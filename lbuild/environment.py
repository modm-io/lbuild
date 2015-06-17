#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import shutil

from . import exception

class Option:
    
    def __init__(self, name, description, value):
        if ":" in name:
            raise exception.BlobException("Character ':' is not allowed in options name '%s'" % name)
        
        self.name = name
        self.description = description
        self._value = value
    
    def _get_value(self):
        return self._value

    def _set_value(self, value):
        self._value = value
    
    value = property(_get_value, _set_value)


class BooleanOption(Option):
    
    def __init__(self, name, description, value):
        self._validate_value(value)
        Option.__init__(self, name, description, value)
    
    def _get_value(self):
        return self._value

    def _set_value(self, value):
        self._value = self._validate_value(value)
    
    value = property(_get_value, _set_value)

    def _validate_value(self, value):
        if value is None:
            return value
        elif isinstance(value, bool):
            return value
        elif str(value).lower() in ['true', 'yes', '1']:
            return True
        elif str(value).lower() in ['false', 'no', '0']:
            return False
        
        raise exception.BlobException("Value '%s' (%s) of option '%s' must be boolean" % 
                                      (value, type(value).__name__, self.name))


class NumericOption(Option):
    
    def __init__(self, name, description, value):
        self._validate_value(value)
        Option.__init__(self, name, description, value)
    
    def _get_value(self):
        return self._value

    def _set_value(self, value):
        self._value = self._validate_value(value)
    
    value = property(_get_value, _set_value)

    def _validate_value(self, value):
        if value is None:
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return int(value, 0)
            except:
                pass
        
        raise exception.BlobException("Value '%s' (%s) of option '%s' must be numeric" % 
                                      (value, type(value).__name__, self.name))


def _copytree(src, dst, ignore=None):
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
                _copytree(s, d, ignore)
            else:
                if not os.path.exists(d) or os.stat(src).st_mtime - os.stat(dst).st_mtime > 1:
                    shutil.copy2(s, d)

class Environment:
    
    def __init__(self, options, modulepath, outpath):
        self.options = options
        self.__modulepath = modulepath
        self.__outpath = outpath
    
    def copy(self, src, dest, ignore=None):
        """
        Copy file or directory from the modulepath to the buildpath.
        
        If src or dest is a relative path it will be relocated to the
        module/buildpath. Absolute paths are not changed.
        """
        srcpath = src if os.path.isabs(src) else os.path.join(self.__modulepath, src)
        destpath = dest if os.path.isabs(dest) else os.path.join(self.__outpath, dest)
        
        if os.path.isdir(srcpath):
            _copytree(srcpath, destpath, ignore)
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
    
    
    def __getitem__(self, key):
        return self.options[key]

    def __repr__(self): 
        return repr(self.options)

    def __len__(self): 
        return len(self.options)
