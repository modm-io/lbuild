#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import pkgutil
import logging
from lxml import etree

import lbuild.module
import lbuild.environment

from .exception import BlobException
from .exception import BlobOptionFormatException

from . import repository
from . import utils

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
                          configfilename: str,
                          repofilenames=None):
        if repofilenames is not None:
            for repofile in utils.listify(repofilenames):
                self.parse_repository(repofile)

        if configfilename is not None:
            configpath = os.path.dirname(configfilename)

            rootnode = self._load_and_verify_configuration(configfilename)
            for path_node in rootnode.iterfind("repositories/folder/path"):
                repository_path = path_node.text
                repository_filename = os.path.realpath(os.path.join(configpath, repository_path))
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
    def _load_and_verify_configuration(configfile):
        """
        Verify the XML structure.
        """
        try:
            LOGGER.debug("Parse configuration '%s'", configfile)
            xmlroot = etree.parse(configfile)

            xmlschema = etree.fromstring(pkgutil.get_data('lbuild', 'resources/configuration.xsd'))

            schema = etree.XMLSchema(xmlschema)
            schema.assertValid(xmlroot)

            xmltree = xmlroot.getroot()
        except OSError as error:
            raise BlobException(error)
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as error:
            raise BlobException("Error while parsing xml-file '{}': "
                                "{}".format(configfile, error))
        return xmltree

    @staticmethod
    def parse_configuration(configfile):
        """
        Parse the configuration file.

        This file contains information about which modules should be included
        and how they are configured.

        Returns:
            tuple with the names of the requested modules and the selected options.
        """
        xmltree = Parser._load_and_verify_configuration(configfile)

        requested_modules = []
        for modules_node in xmltree.findall('modules'):
            for module_node in modules_node.findall('module'):
                modulename = module_node.text
                lbuild.module.verify_module_name(modulename)

                LOGGER.debug("- require module '%s'", modulename)
                requested_modules.append(modulename)

        config_options = {}
        for option_node in xmltree.find('options').findall('option'):
            try:
                config_options[option_node.attrib['name']] = option_node.attrib['value']
            except KeyError:
                config_options[option_node.attrib['name']] = option_node.text

        return (requested_modules, config_options)

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
        for option_name, option_value in config_options.items():
            self._overwrite_repository_options(repo_options_by_full_name,
                                               repo_options_by_option_name,
                                               option_name, option_value)

        # Overwrite again with the values for the command line.
        if cmd_options is not None:
            for option_name, option_value in cmd_options.items():
                self._overwrite_repository_options(repo_options_by_full_name,
                                                   repo_options_by_option_name,
                                                   option_name, option_value)
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
            for modulefile in repo._module_files:
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
    def find_module(modules, modulename):
        """ Get the module representation from a module name.

        The name can either be fully qualified or have an empty repository
        string. In the later case all repositories are searched for the module
        name. An error is raised in case multiple repositories are found.

        Args:
            modulename :  Name of the module in the format
                          'repository:module:submodule:...'.
                          Each part but the last can be an empty string.
        """
        canidates = []

        target_parts = modulename.split(":")
        target_depth = len(target_parts)
        if target_depth < 2:
            raise BlobException("Invalid module name '{}'.".format(modulename))

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
        elif len(found) > 1:
            raise BlobException("Name '{}' is ambiguous "
                                "between '{}'.".format(modulename,
                                                       "', '".join(found)))
        return found[0]

    @staticmethod
    def resolve_dependencies(modules, requested_module_names):
        """
        Resolve dependencies by adding missing modules.
        """
        selected_modules = []
        for modulename in requested_module_names:
            module = Parser.find_module(modules, modulename)
            selected_modules.append(module)

        current = selected_modules
        while 1:
            additional = []
            for module in current:
                for dependency_name in module.dependencies:
                    dependency = Parser.find_module(modules, dependency_name)

                    if dependency not in selected_modules and \
                            dependency not in additional:
                        additional.append(dependency)
            if not additional:
                # Abort if no new dependencies are being found
                break
            selected_modules.extend(additional)
            current = additional
            additional = []

        return selected_modules

    def merge_module_options(self, build_modules, config_options):
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

        for name, value in config_options.items():
            target_parts = name.split(":")
            target_depth = len(target_parts)

            if target_depth < 3:
                # Option is a repository option
                continue

            found_options = []
            for canidate_parts, canidate_option in canidates[target_depth]:
                for target, canidate in zip(target_parts, canidate_parts):
                    if target == "" or target == "*":
                        continue
                    elif target != canidate:
                        break
                else:
                    found_options.append(canidate_option)

            if len(found_options) == 0:
                raise BlobException("Option '{}' not found!".format(name))

            for found_option in found_options:
                found_option.value = value

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
    def build_modules(outpath, build_modules, repo_options, module_options):
        """
        Go through all to build and call their 'build' function.
        """
        Parser.verify_options_are_defined(module_options)
        for module in build_modules:
            option_resolver = lbuild.module.OptionNameResolver(module.repository,
                                                               module,
                                                               repo_options,
                                                               module_options)
            env = lbuild.environment.Environment(option_resolver, module.path, outpath)
            # TODO add exception handling
            module.functions["build"](env)

    @staticmethod
    def format_commandline_options(cmd_options):
        cmd = {}
        for option in cmd_options:
            parts = option.split('=')
            cmd[parts[0]] = parts[1]
        return cmd

    def configure_and_build_library(self, configfile, outpath, cmd_options=None):
        cmd_options = [] if cmd_options is None else cmd_options

        selected_modules, config_options = self.parse_configuration(configfile)

        commandline_options = self.format_commandline_options(cmd_options)
        repo_options = self.merge_repository_options(config_options, commandline_options)

        modules = self.prepare_repositories(repo_options)
        build_modules = self.resolve_dependencies(modules, selected_modules)
        module_options = self.merge_module_options(build_modules, config_options)

        self.build_modules(outpath, build_modules, repo_options, module_options)
