#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from . import environment
from parser import ParserError

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
        
        self.name = None
        self.description = ""
        
        self.functions = {}
    
    def set_name(self, name):
        self.name = name
    
    def set_description(self, description):
        self.description = description
    
    def add_option(self, name, description, default=None):
        """Define new option for this module.
        
        The module options only influence the build process but not the
        selection and dependencies of modules.
        """
        if ":" in name:
            raise ParserError("Character ':' is not allowed in options name '%s'" % name)
        self.options[name] = environment.Option(name, description, default)
    
    def depends(self, dependency):
        pass
