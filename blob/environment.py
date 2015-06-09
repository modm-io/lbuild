#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import shutil

from . import exception

class Option:
    
    def __init__(self, name, description, value):
        self.name = name
        self.description = description
        self.value = value


class Environment:
    
    def __init__(self):
        self.modules = {}
    
    def get_module(self, modulename):
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
            for name, module in self.modules.items():
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
                return self.modules[modulename]
            except KeyError:
                raise exception.BlobException("Module '%s' not found." % modulename)
        

class ModuleEnvironment:
    
    def copy(self, src, dest, ignore=None):
        """
        Copy file or directory from the __modulepath to the buildpath.
        
        If src or dest is a relative path it will be relocated to the
        module/buildpath. Absolute paths are not changed.
        """
        srcpath = src if os.path.isabs(src) else os.path.join(self.__modulepath, src)
        destpath = dest if os.path.isabs(dest) else os.path.join(self.__outpath, dest)
        
        if os.path.isdir(srcpath):
            self.__copytree(srcpath, destpath, ignore)
        else:
            shutil.copy2(srcpath, destpath)
    
    def template(self, src, dest, subsititutions={}):
        """
        Uses the Jinja2 template engine to generate files.
        """
        pass
    
    def modulepath(self, *path):
        """Relocate given path to the path of the module file."""
        return os.path.join(self.__modulepath, *path)
    
    def outpath(self, *path):
        """Relocate given path to the output path."""
        return os.path.join(self.__outpath, *path)
    
    def __copytree(self, src, dst, ignore=None):
        """
        Implementation of shutil.copytree that overwrites files instead
        of aborting.
        """
        if not os.path.exists(dst):
            os.makedirs(dst)
        files = os.listdir(src)
        if ignore is not None:
            ignored = ignore(src, files)
        else:
            ignored = set()
        for f in files:
            if f not in ignored:
                s = os.path.join(src, f)
                d = os.path.join(dst, f)
                if os.path.isdir(s):
                    self.__copytree(s, d, ignore)
                else:
                    if not os.path.exists(d) or os.stat(src).st_mtime - os.stat(dst).st_mtime > 1:
                        shutil.copy2(s, d)
