#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import glob
import parser

def listify(node):
    return [node,] if (not isinstance(node, list)) else node

class Repository:
    
    def __init__(self, path):
        # Path to the repository file. All relative paths refer to this path.
        self.path = path
        self.name = ""
        self.module_files = []
    
    def set_name(self, name):
        self.name = name
    
    def _relocate(self, path):
        # relocate relative paths to the path of the repository
        # configuration file.
        if not os.path.isabs(path):
            path = os.path.join(self.path, path)
        return path
    
    def glob(self, pattern):
        pattern = self._relocate(pattern)
        return glob.glob(pattern)
    
    def add_modules(self, modules):
        module_files = listify(modules)
        
        for file in module_files:
            file = self._relocate(file)
            
            if not os.path.isfile(file):
                raise parser.ParserError("Module file not found '%s'" % file)
            
            self.module_files.append(file)
    
    def find_modules(self, modulefile="module.lb"):
        for path, _, files in os.walk(self.path):
            if modulefile in files:
                self.module_files.append(os.path.join(path, modulefile))

