#!/usr/bin/env python3
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import logging

import lbuild.module
import lbuild.environment

from .exception import BlobException
from .exception import BlobOptionFormatException

from . import repository
from . import utils
from . import config

LOGGER = logging.getLogger('lbuild.parser')


class Parser:

    def __init__(self):
        # All repositories
        # Name -> Repository()
        self.repositories = {}
        self.modules = {}

        # All modules which are available with the given set of
        # configuration options.
        #
        # Only available after prepare_modules() has been called.
        #
        # Module name -> Module()
        self.available_modules = {}

    def load_repositories(self,
                          configuration: config.Configuration,
                          repofilenames=None):
        if repofilenames is not None:
            for repofile in utils.listify(repofilenames):
                self.parse_repository(repofile)
        
        for repository_filename in configuration.repositories:
            self.parse_repository(repository_filename)

    def parse_repository(self, repofilename: str) -> repository.Repository:
        """
        Parse the given repository file.

        Executes the 'prepare' function to populate the repository
        structure.
        """
        repo = repository.Repository.parse_repository(repofilename)

        if repo.name in self.repositories:
            raise BlobException("Repository name '{}' is ambiguous. "
                                "Name must be unique.".format(repo.name))
        else:
            self.repositories[repo.name] = repo
        return repo

    @staticmethod
    def _overwrite_repository_options(options_full_name,
                                      options_option_name,
                                      option_name,
                                      option_value):
        try:
            name_parts = option_name.split(':')
            if len(name_parts) == 2:
                # repository option
                repo_name, option_part = name_parts

                if repo_name == "" or repo_name == "*":
                    key = option_part
                    for option in options_option_name[key]:
                        option.value = option_value
                else:
                    key = option_name
                    options_full_name[key].value = option_value
            elif len(name_parts) < 2:
                raise BlobOptionFormatException(option_name)
        except KeyError:
            raise BlobException("Repository option '{}' not found in any "
                                "repository.".format(option_name))

    def merge_repository_options(self, config_options, cmd_options=None):
        repo_options_by_full_name = {}
        repo_options_by_option_name = {}

        # Get all the repository options and store them in a
        # dictionary with their full qualified name ('repository:option').
        for repo_name, repo in self.repositories.items():
            for config_name, value in repo.options.items():
                name = "%s:%s" % (repo_name, config_name)
                repo_options_by_full_name[name] = value

                # Add an additional reference to find options without
                # the repository name but only but option name
                option_list = repo_options_by_option_name.get(config_name, [])
                option_list.append(value)
                repo_options_by_option_name[config_name] = option_list

        # Overwrite the values in the options with the values provided
        # in the configuration file
        for option in config_options:
            self._overwrite_repository_options(repo_options_by_full_name,
                                               repo_options_by_option_name,
                                               option.name, option.value)

        # Overwrite again with the values for the command line.
        if cmd_options is not None:
            for option in cmd_options:
                self._overwrite_repository_options(repo_options_by_full_name,
                                                   repo_options_by_option_name,
                                                   option.name, option.value)
        return repo_options_by_full_name

    def prepare_repositories(self,
                             repo_options):
        """ Prepare and select modules which are available given the set of
        repository repo_options.

        Returns:
            Dict of modules, key is the qualified module name.
        """
        self.verify_options_are_defined(repo_options)
        for repo in self.repositories.values():
            repo.functions["prepare"](repo,
                                      repository.OptionNameResolver(repo,
                                                                    repo_options))

            # Parse the modules inside this repository
            for modulefile in repo.module_files:
                module = lbuild.module.Module.parse_module(repo, modulefile)
                available = module.prepare(repo_options)
                self.available_modules.update(available)

        # Update the list of modules. Must be done after the prepare loop,
        # because submodules are only added there.
        for repo in self.repositories.values():
            for module in repo.modules.values():
                self.modules[module.fullname] = module

        return self.available_modules

    @staticmethod
    def find_modules(modules, modulename):
        """ Get the module representation from a module name.

        The name can either be fully qualified, have an empty repository/module
        string or use a '*'. In the later two cases all repositories/modules are
        searched for the module name.

        It is also possible to use a double star ('**') as last entry in module
        name. In this all modules at this depth including their submodules
        are selected.

        E.g. modules "a:b", "a:c" and "a:c:d" are available. The name "a:*"
        selects "a:b" and "a:c" but not "a:c:d" while "a:**" would
        select all three.

        Args:
        modulename -- Name of the module in the format
            'repository:module:submodule:...'.
            Each part but the last can be an empty string.

        Returns:
            List of possible modules.
        """
        lbuild.module.verify_module_name(modulename)

        canidates = []

        target_parts = modulename.split(":")
        target_depth = len(target_parts)

        if target_parts[-1] == "**":
            # Remove the double star entry
            target_parts = target_parts[:-1]

            for module in modules.values():
                parts = module.fullname.split(":")
                depth = len(parts)
                if depth >= target_depth:
                    parts = parts[:target_depth]
                    canidates.append((parts, module))
        else:
            for module in modules.values():
                parts = module.fullname.split(":")
                depth = len(parts)
                if depth == target_depth:
                    canidates.append((parts, module))

        found = []
        for parts, module in canidates:
            for target, canidate in zip(target_parts, parts):
                if target == "" or target == "*":
                    continue
                elif target != canidate:
                    break
            else:
                found.append(module)

        if len(found) == 0:
            raise BlobException("Module '{}' not found.".format(modulename))
        return found

    @staticmethod
    def find_module(modules, modulename):
        """
        Find a single module.

        Similar to find_modules(...) but returns only a single module and
        raised an exception in case multiple modules are found.

        Return:
            Single module corresponding to the module name.
        """
        found = Parser.find_modules(modules, modulename)
        if len(found) > 1:
            raise BlobException("Name '{}' is ambiguous "
                                "between '{}'.".format(modulename,
                                                       "', '".join([str(x) for x in found])))
        return found[0]

    @staticmethod
    def resolve_dependencies(modules, requested_module_names):
        """
        Resolve dependencies by adding missing modules.
        """
        selected_modules = []
        for modulename in requested_module_names:
            module_list = Parser.find_modules(modules, modulename)

            # Only add modules which are not already selected
            for module in module_list:
                if module not in selected_modules:
                    selected_modules.append(module)

        LOGGER.info("Selected modules: %s",
                    ", ".join(sorted([module.fullname for module in selected_modules])))

        current = selected_modules
        while True:
            additional = []
            for module in current:
                for dependency_name in module.dependencies:
                    dependency = Parser.find_module(modules, dependency_name)

                    if dependency not in selected_modules and \
                            dependency not in additional:
                        LOGGER.debug("Add dependency: %s",
                                     dependency.fullname)
                        additional.append(dependency)
            if not additional:
                # Abort if no new dependencies are being found
                break
            selected_modules.extend(additional)
            current = additional
            additional = []

        return selected_modules

    @staticmethod
    def merge_module_options(build_modules, config_options):
        """
        Return the list of options used for building the selected modules.

        Returns:
            Dictionary mapping the full qualified option name to the option
            object.
        """
        canidates = {}
        options = {}
        for module in build_modules:
            for option in module.options.values():
                fullname = ":".join([module.fullname,
                                     option.name])
                options[fullname] = option

                parts = fullname.split(":")
                depth = len(parts)
                canidate_list = canidates.get(depth, [])
                canidate_list.append([parts, option])
                canidates[depth] = canidate_list

        for option in config_options:
            target_parts = option.name.split(":")
            target_depth = len(target_parts)

            if target_depth < 3:
                # Option is a repository option
                continue

            found_options = []
            for canidate_parts, canidate_option in canidates.get(target_depth, []):
                for target, canidate in zip(target_parts, canidate_parts):
                    if target == "" or target == "*":
                        continue
                    elif target != canidate:
                        break
                else:
                    found_options.append(canidate_option)

            if len(found_options) == 0:
                LOGGER.warning("Option '%s' not found in selected modules!", option.name)

            for found_option in found_options:
                found_option.value = option.value

        return options

    @staticmethod
    def verify_options_are_defined(options):
        """
        Check that all given options have an assigned value.
        """
        for fullname, option in options.items():
            if option.value is None:
                raise BlobException("Unknown value for option '{}'. Please "
                                    "provide a value in the configuration file "
                                    "or on the command line.".format(fullname))

    @staticmethod
    def build_modules(outpath, build_modules, repo_options, module_options, buildlog):
        """
        Go through all to build and call their 'build' function.
        """
        Parser.verify_options_are_defined(module_options)
        all_modules = {m.fullname: m for m in build_modules}

        # Build all modules in reversed alphabetical order. This enforces
        # that the submodules are always build before their parent modules.
        for module in sorted(build_modules, reverse=True):
            option_resolver = lbuild.module.OptionNameResolver(module.repository,
                                                               module,
                                                               repo_options,
                                                               module_options)
            module_resolver = lbuild.module.ModuleNameResolver(module.repository,
                                                               module,
                                                               all_modules)
            env = lbuild.environment.Environment(option_resolver,
                                                 module_resolver,
                                                 module,
                                                 outpath,
                                                 buildlog)
            # TODO add exception handling
            module.functions["build"](env)

    def configure_and_build_library(self, configfile, outpath, cmd_options=None):
        cmd_options = [] if cmd_options is None else cmd_options

        configuration = config.Configuration.parse_configuration(configfile)

        commandline_options = self.format_commandline_options(cmd_options)
        repo_options = self.merge_repository_options(configuration.options, commandline_options)

        modules = self.prepare_repositories(repo_options)
        build_modules = self.resolve_dependencies(modules, configuration.selected_modules)
        module_options = self.merge_module_options(build_modules, configuration.options)

        log = lbuild.buildlog.BuildLog()
        self.build_modules(outpath, build_modules, repo_options, module_options, log)
