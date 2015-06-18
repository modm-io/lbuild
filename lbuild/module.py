#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from . import environment
from .exception import BlobException
from . import utils

class OptionNameResolver:
    
    def __init__(self, repository, module, repo_options, module_options):
        self.repository = repository
        self.module = module
        self.repo_options = repo_options
        self.module_options = module_options
    
    def __getitem__(self, key):
        o = key.split(":")
        
        try:
            if len(o) == 2:
                repo, option = o
                if repo == "":
                    key = "%s:%s" % (self.repository.name, option)
                
                return self.repo_options[key].value
            elif len(o) == 3:
                repo, module, option = o
                
                if repo == "":
                    repo = self.repository.name
                if module == "":
                    module = self.module.name
                
                key = "%s:%s:%s" % (repo, module, option)
                return self.module_options[key].value
            else:
                raise BlobException("Option name '%s' must contain exactly one (or two) colon " \
                                    "to separate repository(, module) and option name.")
        except KeyError:
            raise BlobException("Unknown option name '%s'" % key)

    def __repr__(self):
        # Create representation of merged module and repository options
        o = self.module_options.copy()
        o.update(self.repo_options)
        
        return repr(o)

    def __len__(self): 
        return len(self.module_options) + len(self.repo_options)


class Module:
    
    def __init__(self, repository, filename, path):
        """Create new module definition.
        
        Args:
            repository : Parent repository of the module.
            filename   : Full path of the module file.
            path       : Path to the module file. Used as base for relative
                paths during the building step of the module.
        """ 
        self.repository = repository
        self.filename = filename
        self.path = path
        
        # Module name without repository
        self.name = None
        # Full qualified name ('repository:module')
        self.full_name = None
        
        self.description = ""
        
        # Required functions declared in the module configuration file
        self.functions = {}
        
        # List of module names this module depends upon
        self.dependencies = []
        
        # OptionNameResolver defined in the module configuration file. These options are
        # configurable through the project configuration file.
        self.options = {}
    
    def set_name(self, name):
        self.name = name
        self.full_name = "%s:%s" % (self.repository.name, name)
    
    def set_description(self, description):
        self.description = description
    
    def add_option(self, name, description, default=None):
        """Define new option for this module.
        
        The module options only influence the build process but not the
        selection and dependencies of modules.
        """
        self._check_for_duplicates(name)
        self.options[name] = environment.Option(name, description, default)
    
    def add_boolean_option(self, name, description, default=None):
        self._check_for_duplicates(name)
        self.options[name] = environment.BooleanOption(name, description, default)
    
    def add_numeric_option(self, name, description, default=None):
        self._check_for_duplicates(name)
        self.options[name] = environment.NumericOption(name, description, default)
    
    def _check_for_duplicates(self, name):
        if name in self.options:
            raise BlobException("Option name '%s' is already defined" % name)
    
    def depends(self, dependencies):
        for dependency in utils.listify(dependencies):
            if len(dependency.split(':')) != 2:
                raise BlobException("Modulename '%s' must contain exactly one ':' as " \
                                    "separator between repository and module name" % dependency)
            self.dependencies.append(dependency)
