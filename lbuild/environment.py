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
import shutil
import textwrap
import jinja2

from .exception import BlobException

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

def filter_wordwrap(value, width=79):
    return '\n\n'.join([textwrap.fill(s, width) for s in value.split('\n\n')])

def filter_indent(value, level=0):
    return ('\n' + ' ' * level).join(value.split('\n'))

def filter_pad(value, min_width):
    tab_width = 4
    tab_count = (min_width / tab_width - len(value) / tab_width) + 1
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


class Environment:

    def __init__(self, options, modulepath, outpath):
        self.options = options
        self.__modulepath = modulepath
        self.__outpath = outpath
        
        self.outbasepath = None

    def copy(self, src, dest=None, ignore=None):
        """
        Copy file or directory from the modulepath to the buildpath.

        If src or dest is a relative path it will be relocated to the
        module/buildpath. Absolute paths are not changed.
        
        If dest is empty the same name as src is used (relocated to
        the output path).
        """
        if dest is None:
            dest = src
        
        srcpath = src if os.path.isabs(src) else self.modulepath(src)
        destpath = dest if os.path.isabs(dest) else self.outpath(dest)

        if os.path.isdir(srcpath):
            _copytree(srcpath, destpath, ignore)
        else:
            if not os.path.exists(os.path.dirname(destpath)):
                os.makedirs(os.path.dirname(destpath))
            shutil.copy2(srcpath, destpath)

    @staticmethod
    def ignore_files(*files):
        return shutil.ignore_patterns(*files)

    def template(self, src, dest, substitutions=None):
        """ Uses the Jinja2 template engine to generate files. """
        if substitutions is None:
            substitutions = {}

        global_substitutions = {
            'time': time.strftime("%d %b %Y, %H:%M:%S", time.localtime()),
            'options': self.options,
        }

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

        loader.filters['modm.wordwrap'] = filter_wordwrap
        loader.filters['modm.indent'] = filter_indent
        loader.filters['modm.pad'] = filter_pad
        loader.filters['modm.values'] = filter_values
        loader.filters['modm.split'] = filter_split

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
        return os.path.join(self.__outpath, self.outbasepath, *path)


    def __getitem__(self, key):
        return self.options[key]

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)
