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
import jinja2

from . import filter
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

    def template(self, src, dest=None, substitutions=None, filters=None):
        """
        Uses the Jinja2 template engine to generate files.

        If dest is empty the same name as src is used (relocated to
        the output path).
        """
        if substitutions is None:
            substitutions = {}

        if dest is None:
            dest = src

        global_substitutions = {
            'time': time.strftime("%d %b %Y, %H:%M:%S", time.localtime()),
            'options': self.options,
        }

        # Overwrite jinja2 Environment in order to enable relative paths
        # since this runs locally that should not be a security concern
        # Code from:
        # http://stackoverflow.com/questions/8512677/how-to-include-a-template-with-relative-path-in-jinja2
        class RelEnvironment(jinja2.Environment):
            """
            Override join_path() to enable relative template paths.

            Take care of paths. Jinja seems to use '/' as path separator in
            templates.
            """
            def join_path(self, template, parent):
                d = os.path.join(os.path.dirname(parent), template)
                return os.path.normpath(d)

        environment = RelEnvironment(loader=jinja2.FileSystemLoader(self.__modulepath),
                                                                    extensions=['jinja2.ext.do'])

        environment.filters['lbuild.wordwrap'] = filter.wordwrap
        environment.filters['lbuild.indent'] = filter.indent
        environment.filters['lbuild.pad'] = filter.pad
        environment.filters['lbuild.values'] = filter.values
        environment.filters['lbuild.split'] = filter.split
        environment.filters['lbuild.listify'] = filter.listify

        if filters is not None:
            environment.filters.update(filters)

        # Jinja2 Line Statements
        environment.line_statement_prefix = '%%'
        environment.line_comment_prefix = '%#'

        try:
            template = environment.get_template(src, globals=global_substitutions)
            output = template.render(substitutions)
        except jinja2.TemplateNotFound as error:
            raise BlobException('Failed to retrieve Template: %s' % error)
        except (jinja2.exceptions.TemplateAssertionError,
                jinja2.exceptions.TemplateSyntaxError) as error:
            raise BlobException("Error in template '{}:{}':\n"
                                " {}: {}".format(error.filename,
                                                 error.lineno,
                                                 error.__class__.__name__,
                                                 error))
        except jinja2.exceptions.UndefinedError as error:
            raise BlobException("Error in template '{}':\n"
                                " {}: {}".format(self.modulepath(src),
                                                 error.__class__.__name__,
                                                 error))
            print(dir(error))

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
        if self.outbasepath is None:
            return os.path.join(self.__outpath, *path)
        else:
            return os.path.join(self.__outpath, self.outbasepath, *path)


    def __getitem__(self, key):
        return self.options[key]

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)
