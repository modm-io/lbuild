#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from . import environment
from . import exception
from . import utils
from blob import repository

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
        
        # Options defined in the module configuration file. These options are
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
        if ":" in name:
            raise exception.BlobException("Character ':' is not allowed in options name '%s'" % name)
        if name in self.options:
            raise exception.BlobException("Option name '%s' is already defined" % name)
        
        self.options[name] = environment.Option(name, description, default)
    
    def depends(self, dependencies):
        for dependency in utils.listify(dependencies):
            if len(dependency.split(':')) != 2:
                raise exception.BlobException("Modulename '%s' must contain exactly one ':' as " \
                                              "separator between repository and module name" % dependency)
            self.dependencies.append(dependency)
