#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import glob

from . import exception
from . import utils
from . import environment

class Options:
    
    def __init__(self, repository, options):
        self.repository = repository
        self.options = options
    
    def __getitem__(self, key):
        o = key.split(":")
        if len(o) != 2:
            raise exception.BlobException("Option name '%s' must contain exactly one colon " \
                                          "to separate repository and option name.")
        repo, option = o
        if repo == "":
            key = "%s:%s" % (self.repository.name, option)
        
        return self.options[key].value
        
    def __repr__(self): 
        return repr(self.options)

    def __len__(self): 
        return len(self.options)


class Repository:
    
    def __init__(self, path):
        # Path to the repository file. All relative paths refer to this path.
        self.path = path
        self.name = None
        
        # Dict of modules, using the filename as the key
        self.modules = {}
        
        # Name -> Option()
        self.options = {}
    
    def set_name(self, name):
        """Set name of the repository."""
        self.name = name
    
    def _relocate(self, path):
        """
        Relocate relative paths to the path of the repository
        configuration file.
        """
        if not os.path.isabs(path):
            path = os.path.join(self.path, path)
        return os.path.normpath(path)
    
    def glob(self, pattern):
        pattern = self._relocate(pattern)
        return glob.glob(pattern)
    
    def add_modules(self, modules):
        """
        Add one or more module files.
        
        Args:
            modules: List of filenames
        """
        module_files = utils.listify(modules)
        
        for file in module_files:
            file = self._relocate(file)
            
            if not os.path.isfile(file):
                raise exception.BlobException("Module file not found '%s'" % file)
            
            self.modules[file] = None
    
    def find_modules(self, basepath="", modulefile="module.lb"):
        """
        Find all module files following a specific pattern.
        
        Args:
            basepath   : Rootpath for the search.
            modulefile : Filename of the module files to search
                for (default: "module.lb").
        """
        basepath = self._relocate(basepath)
        for path, _, files in os.walk(basepath):
            if modulefile in files:
                self.modules[os.path.normpath(os.path.join(path, modulefile))] = None

    def add_option(self, name, description, default=None):
        """
        Define new repository wide option.
        
        These options can be used by modules to decide whether they are
        available and what options they provide for a specific set of
        repository options.
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
            raise exception.BlobException("Option name '%s' is already defined" % name)