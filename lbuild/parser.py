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
import shutil
import logging
from lxml import etree

import lbuild.module
import lbuild.option
import lbuild.environment

from .exception import BlobException
from .exception import OptionFormatException

from . import repository

LOGGER = logging.getLogger('lbuild.parser')

class Localpath:

    def __init__(self, repository_file):
        self.basepath = os.path.dirname(os.path.realpath(repository_file))

    def __call__(self, *args):
        return os.path.join(self.basepath, *args)

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

    @staticmethod
    def _get_global_functions(local, names):
        """
        Get global functions from the environment.
        """
        functions = {}
        for functionname in names:
            f = local.get(functionname)
            if f is None:
                raise BlobException("No function '{}' found!".format(functionname))
            functions[functionname] = f
        return functions

    def parse_repository(self, repofilename: str) -> repository.Repository:
        """
        Parse the given repository file.

        Executes the 'prepare' function to populate the repository
        structure.
        """
        repo = repository.Repository(os.path.dirname(repofilename))
        try:
            with open(repofilename) as repofile:
                code = compile(repofile.read(), repofilename, 'exec')
                local = {
                    '__file__': repofilename,

                    # The localpath(...) function can be used to create
                    # a local path form the folder of the repository file.
                    'localpath': Localpath(repofilename),

                    'StringOption': lbuild.option.Option,
                    'BooleanOption': lbuild.option.BooleanOption,
                    'NumericOption': lbuild.option.NumericOption,
                    'EnumerationOption': lbuild.option.EnumerationOption,
                }
                exec(code, local)

                repo.functions = self._get_global_functions(local, ['init', 'prepare'])

                # Execution init() function. In this function options are added.
                repo.functions['init'](repo)

                if repo.name is None:
                    raise BlobException("The init(repo) function must set a repository name! "
                                        "Please use the set_name() method.")

        except KeyError as error:
            raise BlobException("Invalid repository configuration file '{}':\n"
                                " {}: {}".format(repofilename,
                                                 error.__class__.__name__,
                                                 error))

        if repo.name in self.repositories:
            raise BlobException("Repository name '{}' is ambiguous. "
                                "Name must be unique.".format(repo.name))

        self.repositories[repo.name] = repo
        return repo

    @staticmethod
    def parse_module(repo: repository.Repository,
                     module_filename: str) -> lbuild.module.Module:
        """
        Parse a specific module file.

        Returns:
            Module() module definition object.
        """
        try:
            with open(module_filename) as f:
                LOGGER.debug("Parse module_filename '%s'", module_filename)
                code = compile(f.read(), module_filename, 'exec')

                local = {
                    # The localpath(...) function can be used to create
                    # a local path form the folder of the repository file.
                    'localpath': Localpath(module_filename),

                    'ignore_patterns': shutil.ignore_patterns,

                    'StringOption': lbuild.option.Option,
                    'BooleanOption': lbuild.option.BooleanOption,
                    'NumericOption': lbuild.option.NumericOption,
                    'EnumerationOption': lbuild.option.EnumerationOption,
                }
                exec(code, local)

                module = lbuild.module.Module(repo,
                                              module_filename,
                                              os.path.dirname(module_filename))

                # Get the required global functions
                module.functions = Parser._get_global_functions(local, ['init', 'prepare', 'build'])

                # Execute init() function from module to get module name
                module.functions['init'](module)

                if module.name is None:
                    raise BlobException("The init(module) function must set a module name! " \
                                        "Please use the set_name() method.")

                LOGGER.info("Found module '%s'", module.name)

                return module
        except Exception as e:
            raise BlobException("While parsing '%s': %s" % (module_filename, e))

    def parse_configuration(self, configfile):
        """
        Parse the configuration file.

        This file contains information about which modules should be included
        and how they are configured.

        Returns:
            tuple with the names of the requested modules and the selected options.
        """
        try:
            LOGGER.debug("Parse configuration '%s'", configfile)
            xmlroot = etree.parse(configfile)

            xmlschema = etree.fromstring(pkgutil.get_data('lbuild', 'resources/library.xsd'))

            schema = etree.XMLSchema(xmlschema)
            schema.assertValid(xmlroot)

            xmltree = xmlroot.getroot()
        except OSError as error:
            raise BlobException(error)
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as error:
            raise BlobException("Error while parsing xml-file '{}': "
                                "{}".format(configfile, error))

        requested_modules = []
        for modules_node in xmltree.findall('modules'):
            for module_node in modules_node.findall('module'):
                modulename = module_node.text
                lbuild.module.verify_module_name(modulename)

                LOGGER.debug("- require module '%s'", modulename)
                requested_modules.append(modulename)

        config_options = {}
        for option_node in xmltree.find('options').findall('option'):
            config_options[option_node.attrib['name']] = option_node.attrib['value']

        return (requested_modules, config_options)

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
        for config_name, value in config_options.items():
            name = config_name.split(':')
            if len(name) == 2:
                # repository option
                repo_name, option_name = name

                if repo_name == "":
                    for option in repo_options_by_option_name[option_name]:
                        option.value = value
                else:
                    repo_options_by_full_name[config_name].value = value
            elif len(name) == 3:
                # module option
                pass
            else:
                raise OptionFormatException(config_name)

        # Overwrite again with the values for the command line.
        if cmd_options is not None:
            for config_name, value in cmd_options.items():
                name = config_name.split(':')
                if len(name) == 2:
                    # repository option
                    repo_name, option_name = name

                    if repo_name == "":
                        for option in repo_options_by_option_name[option_name]:
                            option.value = value
                    else:
                        repo_options_by_full_name[config_name].value = value
                elif len(name) == 3:
                    # module option
                    pass
                else:
                    raise OptionFormatException(config_name)

        return repo_options_by_full_name

    def prepare_repositories(self,
                             repo_options):
        self.verify_options_are_defined(repo_options)
        for repo in self.repositories.values():
            repo.functions["prepare"](repo,
                                      repository.OptionNameResolver(repo,
                                                                    repo_options))

            # Parse the modules inside the repository
            for modulefile, module in repo.modules.items():
                # Parse all modules which are not yet updated
                if module is None:
                    module = self.parse_module(repo, modulefile)
                    repo.modules[modulefile] = module

                    self.modules["%s:%s" % (repo.name, module.name)] = module


    def prepare_modules(self, repo_options):
        """ Prepare and select modules which are available given the set of
        repository repo_options.

        Returns:
            Dict of modules, key is the qualified module name.
        """
        self.verify_options_are_defined(repo_options)
        for repo in self.repositories.values():
            for module in repo.modules.values():
                prepare = module.functions["prepare"]
                available = prepare(module,
                                    repository.OptionNameResolver(repo,
                                                                  repo_options))

                if available:
                    name = "%s:%s" % (repo.name, module.name)
                    self.available_modules[name] = module

        return self.available_modules

    def get_available_module(self, modulename):
        """ Get the module representation from a module name.

        The name can either be fully qualified or have an empty repository
        string. In the later case all repositories are searched for the module
        name. An error is raised in case multiple repositories are found.

        Args:
            modulename :  Name of the module in the format 'repository:available_module'.
                          'repository' can be an empty string.
        """
        repopart, modulepart = modulename.split(':')
        found_module = None
        if repopart == "":
            for name, available_module in self.available_modules.items():
                _, available_modulepart = name.split(':')
                if available_modulepart == modulepart:
                    if found_module is not None:
                        # Found at least an other module in a different
                        # repository with the same name.
                        raise BlobException("Name '{}' is ambiguous. "
                                            "Please specify the repository.".format(modulename))
                    found_module = available_module

            if found_module is None:
                raise BlobException("Module '{}' not found.".format(modulename))
            else:
                return found_module
        else:
            try:
                return self.available_modules[modulename]
            except KeyError:
                raise BlobException("Module '%s' not found." % modulename)

    def resolve_dependencies(self, modules, requested_modules):
        """
        Resolve dependencies by adding missing modules.
        """
        selected_modules = []
        for modulename in requested_modules:
            m = self.get_available_module(modulename)
            selected_modules.append(m)

        current = selected_modules
        while 1:
            additional = []
            for m in current:
                for dependency_name in m.dependencies:
                    dependency = self.get_available_module(dependency_name)

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
            Dictionary mapping the full qualified option name to the option object.
        """
        modules_by_full_name = {}
        modules_by_name = {}
        for module in build_modules:
            modules_by_full_name[module.full_name] = module

            # Add an additional reference to find options without
            # the repository name but only but option name
            module_list = modules_by_name.get(module.name, [])
            module_list.append(module)
            modules_by_name[module.name] = module_list

        # Overwrite the values in the options with the values provided
        # in the configuration file
        for config_name, value in config_options.items():
            name = config_name.split(':')
            if len(name) == 2:
                # repository option -> ignore here
                pass
            elif len(name) == 3:
                # module option
                repo_name, module_name, option_name = name

                modules = []
                # Select modules to which to apply the value
                if module_name == "":
                    if repo_name == "":
                        modules = build_modules
                    else:
                        for module in build_modules:
                            if module.repository.name == repo_name:
                                modules.append(module)
                else:
                    if repo_name == "":
                        modules = modules_by_name[module_name]
                    else:
                        modules = [modules_by_full_name["%s:%s" % (repo_name, module_name)]]

                # Search options within the selected modules
                found = False
                for module in modules:
                    for option in module.options.values():
                        if option_name == option.name:
                            # Set new value
                            option.value = value
                            found = True

                if not found:
                    raise BlobException("Option '%s' not found!" % config_name)
            else:
                raise OptionFormatException(config_name)

        options = {}
        for module in build_modules:
            for option in module.options.values():
                fullname = "%s:%s" % (module.full_name, option.name)
                options[fullname] = option

        return options

    def verify_options_are_defined(self, options):
        """
        Check that all given options have an assigned value.
        """
        for fullname, option in options.items():
            if option.value is None:
                raise BlobException("Unknown value for option '{}'. Please provide "
                                    "a value in the configuration file or on the "
                                    "command line.".format(fullname))

    def build_modules(self, outpath, build_modules, repo_options, module_options):
        """
        Go through all to build and call their 'build' function.
        """
        self.verify_options_are_defined(module_options)
        for module in build_modules:
            option_resolver = lbuild.module.OptionNameResolver(module.repository,
                                                               module,
                                                               repo_options,
                                                               module_options)
            env = lbuild.environment.Environment(option_resolver, module.path, outpath)
            # TODO add exception handling
            module.functions["build"](env)

    def format_commandline_options(self, cmd_options):
        cmd = {}
        for option in cmd_options:
            o = option.split('=')
            cmd[o[0]] = o[1]
        return cmd

    def configure_and_build_library(self, configfile, outpath, cmd_options=[]):
        selected_modules, config_options = self.parse_configuration(configfile)

        commandline_options = self.format_commandline_options(cmd_options)
        repo_options = self.merge_repository_options(config_options, commandline_options)

        self.prepare_repositories(repo_options)
        modules = self.prepare_modules(repo_options)

        build_modules = self.resolve_dependencies(modules, selected_modules)
        module_options = self.merge_module_options(build_modules, config_options)

        self.build_modules(outpath, build_modules, repo_options, module_options)
