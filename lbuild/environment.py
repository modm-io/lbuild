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

import lbuild.filter

from .exception import BlobException


def _copytree(logger, src, dst, ignore=None):
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
    for filename in files:
        if filename not in ignored:
            sourcepath = os.path.join(src, filename)
            destpath = os.path.join(dst, filename)
            if os.path.isdir(sourcepath):
                _copytree(logger, sourcepath, destpath, ignore)
            else:
                starttime = time.time()

                time_diff = os.stat(src).st_mtime - os.stat(dst).st_mtime
                if not os.path.exists(destpath) or time_diff > 1:
                    shutil.copy2(sourcepath, destpath)

                endtime = time.time()
                total = endtime - starttime
                logger(sourcepath, destpath, total)


class Environment:

    def __init__(self, options, module, outpath, buildlog):
        self.options = options
        self.__module = module
        self.__modulepath = module.path
        self.__outpath = outpath

        self.__buildlog = buildlog
        self.__template_environment = None
        self.__template_environment_filters = None

        self.outbasepath = None
        self.substitutions = {}

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

        starttime = time.time()

        srcpath = os.path.normpath(src if os.path.isabs(src) else self.modulepath(src))
        destpath = os.path.normpath(dest if os.path.isabs(dest) else self.outpath(dest))

        if os.path.isdir(srcpath):
            _copytree(lambda src, dest, time: self.__buildlog.log(self.__module, src, dest, time),
                      srcpath,
                      destpath,
                      ignore)
        else:
            if not os.path.exists(os.path.dirname(destpath)):
                os.makedirs(os.path.dirname(destpath))
            shutil.copy2(srcpath, destpath)

            endtime = time.time()
            total = endtime - starttime
            self.__buildlog.log(self.__module, srcpath, destpath, total)

    @staticmethod
    def ignore_files(*files):
        return shutil.ignore_patterns(*files)

    def __reload_template_environment(self, filters):
        if self.__template_environment_filters == filters:
            return

        self.__template_environment_filters = filters
        self.__global_substitutions = {
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
                path = os.path.join(os.path.dirname(parent), template)
                return os.path.normpath(path)

        environment = RelEnvironment(loader=jinja2.FileSystemLoader(self.__modulepath),
                                     extensions=['jinja2.ext.do'],
                                     undefined=jinja2.StrictUndefined)

        environment.filters['lbuild.wordwrap'] = lbuild.filter.wordwrap
        environment.filters['lbuild.indent'] = lbuild.filter.indent
        environment.filters['lbuild.pad'] = lbuild.filter.pad
        environment.filters['lbuild.values'] = lbuild.filter.values
        environment.filters['lbuild.split'] = lbuild.filter.split
        environment.filters['lbuild.listify'] = lbuild.filter.listify

        environment.filters.update(filters)

        # Jinja2 Line Statements
        environment.line_statement_prefix = '%%'
        environment.line_comment_prefix = '%#'

        self.__template_environment = environment

    @property
    def template_environment(self):
        if self.__template_environment is None:
            self.__reload_template_environment({})
        return self.__template_environment

    def template(self, src, dest=None, substitutions=None, filters=None):
        """
        Uses the Jinja2 template engine to generate files.

        If dest is empty the same name as src is used (relocated to
        the output path).
        """
        starttime = time.time()

        if dest is None:
            # If src ends in ".in" remove that and use the remaing part
            # as new destination.
            parts = src.split(".")
            if parts[-1] == "in":
                dest = ".".join(parts[:-1])
            else:
                dest = src

        if substitutions is None:
            substitutions = {}

        substitutions.update(self.substitutions)
        try:
            if filters is not None:
                # Reload environment if it uses different filters than
                # the previous environment
                self.__reload_template_environment(filters)

            template = self.template_environment.get_template(src, globals=self.__global_substitutions)
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
        except BlobException as error:
            raise BlobException("Error in template '{}': \n"
                                "{}".format(self.modulepath(src), error))

        outfile_name = self.outpath(dest)

        # Create folder structure if it doesn't exists
        if not os.path.exists(os.path.dirname(outfile_name)):
            os.makedirs(os.path.dirname(outfile_name))

        with open(outfile_name, 'w') as outfile:
            outfile.write(output)

        endtime = time.time()
        total = endtime - starttime
        self.__buildlog.log(self.__module, self.modulepath(src), outfile_name, total)

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
