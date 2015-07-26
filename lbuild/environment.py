#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import time
import jinja2
import shutil
import textwrap

from .exception import BlobException

class Option:
    
    def __init__(self, name, description, value):
        if ":" in name:
            raise BlobException("Character ':' is not allowed in options name '%s'" % name)
        
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
        Option.__init__(self, name, description, value)
        self._set_value(value)
    
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
        
        raise BlobException("Value '%s' (%s) of option '%s' must be boolean" % 
                            (value, type(value).__name__, self.name))


class NumericOption(Option):
    
    def __init__(self, name, description, value):
        Option.__init__(self, name, description, value)
        self._set_value(value)
    
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
        
        raise BlobException("Value '%s' (%s) of option '%s' must be numeric" % 
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
        """ Copy file or directory from the modulepath to the buildpath.
        
        If src or dest is a relative path it will be relocated to the
        module/buildpath. Absolute paths are not changed.
        """
        srcpath = src if os.path.isabs(src) else os.path.join(self.__modulepath, src)
        destpath = dest if os.path.isabs(dest) else os.path.join(self.__outpath, dest)
        
        if os.path.isdir(srcpath):
            _copytree(srcpath, destpath, ignore)
        else:
            shutil.copy2(srcpath, destpath)
    
    def ignore_files(self, *files):
        return shutil.ignore_patterns(*files)
    
    def template(self, src, dest, substitutions={}):
        """ Uses the Jinja2 template engine to generate files. """
        global_substitutions = {
            'time': time.strftime("%d %b %Y, %H:%M:%S", time.localtime()),
            'options': self.options,
        }
        
        def filter_wordwrap(value, width=79):
            return '\n\n'.join([textwrap.fill(s, width) for s in value.split('\n\n')])
    
        def filter_indent(value, level=0):
            return ('\n' + '\t' * level).join(value.split('\n'))
    
        def filter_pad(value, min_width):
            tab_width = 4
            tab_count =  (min_width/tab_width - len(value)/tab_width) + 1
            return value + ('\t' * tab_count)
    
        def filter_split(value, delimiter):
            return value.split(delimiter)

        def filter_values(lst, key):
            """ Go through the list of dictionaries and add all the values of
            a certain key to a list.
            """
            values = []
            for item in lst:
                if isinstance(item, dict) and key in item:
                    if item[key] not in values:
                        values.append(item[key])
            return values
    
        # Overwrite jinja2 Environment in order to enable relative paths
        # since this runs locally that should not be a security concern
        # Code from:
        # http://stackoverflow.com/questions/8512677/how-to-include-a-template-with-relative-path-in-jinja2
        class RelEnvironment(jinja2.Environment):
            """Override join_path() to enable relative template paths.
            Take care of paths. Jinja seems to use '/' as path separator in
            templates.
            """
            def join_path(self, template, parent):
                d = os.path.join(os.path.dirname(parent), template)
                return os.path.normpath(d)

        loader = RelEnvironment(loader=jinja2.FileSystemLoader(self.__modulepath),
                                                               extensions=['jinja2.ext.do'])
        
        loader.filters['xpcc.wordwrap'] = filter_wordwrap
        loader.filters['xpcc.indent'] = filter_indent
        loader.filters['xpcc.pad'] = filter_pad
        loader.filters['xpcc.values'] = filter_values
        loader.filters['split'] = filter_split
        
        # Jinja2 Line Statements
        loader.line_statement_prefix = '%%'
        loader.line_comment_prefix = '%#'
        
        try:
            template = loader.get_template(src, globals=global_substitutions)
        except jinja2.TemplateNotFound as e:
            raise BlobException('Failed to retrieve Template: %s' % e)
    
        output = template.render(substitutions)
        
        outfile = self.outpath(dest)
        
        # Create folder structure if it doesn't exists
        if not os.path.exists(os.path.dirname(outfile)):
            os.makedirs(os.path.dirname(outfile))
        
        with open(outfile, 'w') as f:
            f.write(output)
    
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
