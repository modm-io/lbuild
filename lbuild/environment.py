#!/usr/bin/env python3
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import time
import shutil
import fnmatch
import jinja2
import logging

import lbuild.filter

from .exception import BlobException, BlobTemplateException, BlobForwardException


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

    def __init__(self, options, modules, module, outpath, buildlog):
        self.options = options
        self.modules = modules
        self.__module = module
        self.__modulepath = module.path
        self.__repopath = module.repository.path
        self.__outpath = outpath

        self.__buildlog = buildlog
        self.__template_environment = None
        self.__template_environment_filters = None
        self.__template_global_substitutions = {
            'time': time.strftime("%d %b %Y, %H:%M:%S", time.localtime()),
            'options': self.options,
        }

        self.log = logging.getLogger("user." + module.fullname.replace(":", "."))
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

        srcrelpath = os.path.relpath(srcpath, self.__repopath)
        if srcrelpath.startswith(".."):
            raise BlobException("Cannot access files outside of repository!\n"
                                "'{}'".format(srcrelpath))

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
        """
        Ignore file and folder names without checking the full path.

        Example: the following code with ignore all files with the ending `.lb`:
        ```
        env.copy(".", ignore=env.ignore_files("*.lb"))
        ```

        Based on the shutil.ignore_patterns() function.
        """
        return shutil.ignore_patterns(*files)

    @staticmethod
    def ignore_patterns(*patterns):
        """
        Ignore patterns based on the absolute file path.

        Use an `*` at the beginning to match relative paths:
        ```
        env.copy(".", ignore=env.ignore_patterns("*platform/*.lb"))
        ```
        This ignores all files in the `platform` sub-directory with the
        ending `.lb`.
        """
        def check(path, files):
            ignored = set()
            for pattern in patterns:
                for filename in files:
                    if fnmatch.fnmatch(os.path.join(path, filename), pattern):
                        # The copytree function uses only the filename to check
                        # which files should be ignored, not the absolute path.
                        ignored.add(filename)
            return ignored
        return check

    def __reload_template_environment(self, filters):
        if self.__template_environment_filters == filters:
            return

        self.__template_environment_filters = filters

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

        environment = RelEnvironment(loader=jinja2.FileSystemLoader(self.__repopath),
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

        src = self.repopath(src)
        if src.startswith(".."):
            raise BlobException("Cannot access template outside of repository!\n"
                                "'{}'".format(src))

        if substitutions is None:
            substitutions = {}

        substitutions.update(self.substitutions)
        try:
            if filters is not None:
                # Reload environment if it uses different filters than
                # the previous environment
                self.__reload_template_environment(filters)

            template = self.template_environment.get_template(src, globals=self.__template_global_substitutions)
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
            raise BlobTemplateException("Error in template '{}':\n"
                                        " {}: {}".format(self.modulepath(src),
                                                         error.__class__.__name__,
                                                         error))
        except BlobException as error:
            raise BlobException("Error in template '{}': \n"
                                "{}".format(self.modulepath(src), error))
        except Exception as error:
            raise BlobForwardException("Error in template '{}': \n"
                                       "{}".format(self.modulepath(src), error),
                                       error)

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

    def repopath(self, *path):
        """Relocate given path to the path of the repo file."""
        return os.path.relpath(self.modulepath(*path), self.__repopath)

    def outpath(self, *path):
        """Relocate given path to the output path."""
        if self.outbasepath is None:
            return os.path.join(self.__outpath, *path)
        else:
            return os.path.join(self.__outpath, self.outbasepath, *path)

    def get_generated_local_files(self, filterfunc=None):
        """
        Get all files which have been generated by this module and its
        submodules so far.

        Keyword arguments:
        filterfunc -- Function which is called to determine whether a path
            should be added to the output. If the function returns `True`
            the path is added.
        """
        filenames = []
        operations = self.__buildlog.get_operations_per_module(self.__module.fullname)
        for operation in operations:
            filename = os.path.normpath(os.path.join(os.path.relpath(os.path.dirname(operation.filename_out),
                                                                     self.outpath('.')),
                                                     os.path.basename(operation.filename_out)))
            if filterfunc is None or filterfunc(filename):
                filenames.append(filename)
        return filenames

    def append_metadata(self, key, value):
        """
        Append additional information to the build log which can be used in the
        post-build step to generate additional files/data.
        """
        self.__buildlog.metadata[key].append(value)

    def append_metadata_unique(self, key, value):
        """
        Append additional information build log if it is not already present.

        See:
        - append_metadata
        """
        if value not in self.__buildlog.metadata[key]:
            self.__buildlog.metadata[key].append(value)

    def assert_new_option(self, key):
        """Query whether an option exists."""
        try:
            _ = self.options[key]
            return True
        except BlobException:
            return False

    def get_option(self, key, default=None):
        """
        Get an option value.

        Returns a user configurable default value if the option is not found.
        """
        try:
            return self.options[key]
        except BlobException:
            return default

    def has_module(self, key):
        """Query whether a module exists."""
        try:
            _ = self.modules[key]
            return True
        except BlobException:
            return False

    def __getitem__(self, key):
        """
        Get an option value.

        Raises an exception if the option is not found.
        """
        return self.options[key]

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)
