#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import argparse
import pkgutil
import logging.config
from lxml import etree


import lbuild.module
import lbuild.environment

from . import exception
from . import repository

logger = logging.getLogger('lbuild.parser')

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
    
    def parse_repository(self, repofile):
        repo = repository.Repository(os.path.dirname(repofile))
        try:
            with open(repofile) as f:
                code = compile(f.read(), repofile, 'exec')
                local = {}
                exec(code, local)
                
                prepare = local.get('prepare')
                if prepare is None:
                    raise exception.BlobException("No prepare() function found!")
                
                # Execution prepare() function. In this function modules and
                # options are added. 
                prepare(repo)
                
                if repo.name is None:
                    raise exception.BlobException("The prepare(repo) function must set a repo name! " \
                                                  "Please use the set_name() method.")
        
        except Exception as e:
            raise exception.BlobException("Invalid repository configuration file '%s': %s" % 
                                            (repofile, e))
        
        # Parse the modules inside the repository
        for modulefile, m in repo.modules.items():
            # Parse all modules which are not yet updated
            if m is None:
                m = self._parse_module(repo, modulefile)
                repo.modules[modulefile] = m
                
                self.modules["%s:%s" % (repo.name, m.name)] = m
        
        if repo.name in self.repositories:
            raise exception.BlobException("Repository name '%s' is ambiguous. Name must be unique." % repo.name)
        
        self.repositories[repo.name] = repo
        return repo
    
    def _parse_module(self, repo, modulefile):
        """
        Parse a specific module file.
        
        Returns:
            Module() module definition object.
        """
        try:
            with open(modulefile) as f:
                logger.debug("Parse modulefile '%s'" % modulefile)
                code = compile(f.read(), modulefile, 'exec')
        
                local = {}
                exec(code, local)
                
                m = lbuild.module.Module(repo, modulefile, os.path.dirname(modulefile))
                
                # Get the required global functions
                for functionname in ['init', 'prepare', 'build']:
                    f = local.get(functionname)
                    if f is None:
                        raise exception.BlobException("No function '%s' found!" % functionname)
                    m.functions[functionname] = f
                
                # Execute init() function from module to get module name
                m.functions['init'](m)
                
                if m.name is None:
                    raise exception.BlobException("The init(module) function must set a module name! " \
                                                  "Please use the set_name() method.")
                  
                logger.info("Found module '%s'" % m.name)
                
                return m
        except Exception as e:
            raise exception.BlobException("While parsing '%s': %s" % (modulefile, e))
    
    def parse_configuration(self, configfile):
        """
        Parse the configuration file.
    
        This file contains information about which modules should be included
        and how they are configured.
        
        Returns:
            tuple with the names of the requested modules and the selected options.
        """
        try:
            logger.debug("Parse configuration '%s'" % configfile)
            xmlroot = etree.parse(configfile)
            
            xmlschema = etree.fromstring(pkgutil.get_data('lbuild', 'resources/library.xsd'))
            
            schema = etree.XMLSchema(xmlschema)
            schema.assertValid(xmlroot)
    
            xmltree = xmlroot.getroot()
        except OSError as e:
            raise exception.BlobException(e)
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
            raise exception.BlobException("Error while parsing xml-file '%s': %s" % (configfile, e))
    
        requested_modules = []
        for modules_node in xmltree.findall('modules'):
            for module_node in modules_node.findall('module'):
                modulename = module_node.text
                m = modulename.split(":")
                if len(m) != 2:
                    raise exception.BlobException("Modulename '%s' must contain exactly one ':' as " \
                                                  "separator between repository and module name" % modulename)
                
                logger.debug("- require module '%s'" % modulename)
                requested_modules.append(modulename)
        
        config_options = {}
        for e in xmltree.find('options').findall('option'):
            config_options[e.attrib['name']] = e.attrib['value']
        
        return (requested_modules, config_options)
    
    def merge_repository_options(self, config_options):
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
                    repo_options_by_full_name[name].value = value
            elif len(name) == 3:
                # module option
                pass
            else:
                raise exception.BlobException("Invalid option '%s'" % config_name)
        
        # Check that all option values are set
        for option in repo_options_by_full_name.values():
            if option.value is None:
                raise exception.BlobException("Unknown value for option '%s'." \
                                              "Please provide a value in the configuration file." % option.name)
        
        return repo_options_by_full_name

    def prepare_modules(self, options):
        """
        Prepare and select modules which are available given the set of
        repository options.
        
        Returns:
            Dict of modules, key is the qualified module name.
        """
        for repo in self.repositories.values():
            for m in repo.modules.values():
                available = m.functions["prepare"](m, repository.Options(repo, options))
                
                if available:
                    name = "%s:%s" % (repo.name, m.name)
                    self.available_modules[name] = m
        
        return self.available_modules
    
    def get_available_module(self, modulename):
        """Get the module representation from a module name.
        
        The name can either be fully qualified or have an empty repository
        string. In the later case all repositories are searched for the module
        name. An error is raised in case multiple repositories are found.
        
        Args:
            modulename :  Name of the module in the format 'repository:module'.
                          'repository' can be an empty string.
        """
        repopart, modulepart = modulename.split(':')
        m = None
        if repopart == "":
            for name, module in self.available_modules.items():
                _, n = name.split(':')
                if n == modulepart:
                    if m is not None:
                        raise exception.BlobException("Name '%s' is ambiguous. " \
                                                      "Please specify the repository." % modulename)
                    m = module
            if m is None:
                raise exception.BlobException("Module '%s' not found." % modulename)
            else:
                return m
        else:
            try:
                return self.available_modules[modulename]
            except KeyError:
                raise exception.BlobException("Module '%s' not found." % modulename)
    
    def resolve_dependencies(self, modules, requested_modules):
        """Resolve dependencies by adding missing modules"""
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
        Returns the list of options used for building the selected modules.
        
        Raises an exception if not all options have assigned values.
        
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
                    raise exception.BlobException("Option '%s' not found!" % config_name)
            else:
                raise exception.BlobException("Invalid option '%s'" % config_name)
        
        options = {}
        # Check that all option values are set
        for module in build_modules:
            for option in module.options.values():
                if option.value is None:
                    raise exception.BlobException("Unknown value for option '%s'." \
                                                  "Please provide a value in the configuration file." % option.name)
                fullname = "%s:%s" % (module.full_name, option.name)
                options[fullname] = option
        
        return options
    
    def build_modules(self, outpath, build_modules, repo_options, module_options):
        for module in build_modules:
            options = lbuild.module.Options(module.repository, module, repo_options, module_options)
            env = lbuild.environment.Environment(options, module.path, outpath)
            module.functions["build"](env)

def configure_logger(verbosity):
    logging.config.dictConfig({
        'version': 1,              
        'disable_existing_loggers': False,
        'formatters': {
            'full': {
                #'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                'format': '[%(levelname)s] %(name)s: %(message)s'
            },
            'simple': {
                'format': '%(message)s'
            },
        },
        'handlers': {
            'default': {
                'class':'logging.StreamHandler',
                'formatter': 'full',
            },
        },
        'loggers': {
            '': {                  
                'handlers': ['default'],
                'level': 'DEBUG' if verbosity > 1 else ('INFO' if verbosity == 1 else 'WARNING'),
                'propagate': True  
            }
        }
    })

def main():
    parser = argparse.ArgumentParser(description='Build libraries from source code repositories')
    parser.add_argument('-r', '--repository',
        dest='repositories',
        required=True,
        action='append',
        help='Folder in which modules are located')
    parser.add_argument('-p', '--project',
        dest='project',
        required=True,
        help='Project/library configuration file')
    parser.add_argument('-o', '--__outpath',
        dest='__outpath',
        default='.',
        help='Output path to which the  library will be generated')
    parser.add_argument('-v', '--verbose',
        action='count',
        default = 0,
        dest='verbose')

    args = parser.parse_args()
    
    configure_logger(args.verbose)
    
    try:
        pass
    except exception.BlobException as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)