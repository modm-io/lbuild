#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import time
import shutil
import logging
import zipfile
import tarfile
import tempfile

import jinja2

import lbuild.utils

from .facade import EnvironmentValidateFacade, EnvironmentBuildFacade, EnvironmentPostBuildFacade
from .exception import LbuildException, LbuildTemplateException, LbuildForwardException

SIMULATE = False


def _copyfile(sourcepath, destpath, fn_copy=shutil.copy2):
    """
    Copy a file if the source file time stamp is newer than the destination
    timestamp.
    """
    if not SIMULATE:
        fn_copy(sourcepath, destpath)


def _copytree(logger, src, dst, ignore=None,
              fn_listdir=os.listdir,
              fn_isdir=os.path.isdir,
              fn_copy=shutil.copy2):
    """
    Implementation of shutil.copytree that overwrites files instead
    of aborting.
    """
    files = fn_listdir(src)
    if ignore is not None:
        ignored = ignore(src, files)
    else:
        ignored = set()

    for filename in files:
        if filename not in ignored:
            sourcepath = os.path.join(src, filename)
            destpath = os.path.join(dst, filename)
            if fn_isdir(sourcepath):
                _copytree(logger, sourcepath, destpath, ignore, fn_listdir, fn_isdir, fn_copy)
            else:
                starttime = time.time()
                if not os.path.exists(dst):
                    os.makedirs(dst, exist_ok=True)
                _copyfile(sourcepath, destpath, fn_copy)
                endtime = time.time()
                total = endtime - starttime
                logger(sourcepath, destpath, total)


class Environment:

    def __init__(self, module, buildlog):
        self.options = module.option_value_resolver
        self.queries = module.query_resolver(self.facade_validate)
        self.modules = module.module_resolver
        self.__module = module
        self.__modulepath = module._filepath
        self.__repopath = module.repository._filepath
        self.__outpath = buildlog.outpath if buildlog else None

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

    @property
    def facade_validate(self):
        return EnvironmentValidateFacade(self)

    @property
    def facade_build(self):
        return EnvironmentBuildFacade(self)

    @property
    def facade_post_build(self):
        return EnvironmentPostBuildFacade(self)

    def extract(self, archive_path, src=None, dest=None, ignore=None, metadata=None):

        def wrap_ignore(path, files):
            ignored = lbuild.utils.ignore_patterns(*self.__module._ignore_patterns)(path, files)
            ignored.add(self.__module._filename)
            if ignore:
                ignored |= set(ignore(path, files))
            return ignored

        if src is None:
            src = ""
        if dest is None:
            dest = src
        archive_path = os.path.normpath(
            archive_path if os.path.isabs(archive_path) else self.modulepath(archive_path))

        destpath = os.path.normpath(dest if os.path.isabs(dest) else self.outpath(dest))
        archiverelpath = os.path.relpath(archive_path, self.__repopath)
        if archiverelpath.startswith(".."):
            raise LbuildException("Cannot access files outside of the repository!\n"
                                  "'{}'".format(archiverelpath))

        starttime = time.time()
        is_zip = archive_path.endswith(".zip")
        with (zipfile.ZipFile(archive_path, "r") if is_zip else
              tarfile.TarFile(archive_path, "r")) as archive:

            if is_zip:
                members = archive.namelist()
            else:  # normalize folder names for tarfiles
                members = [m + "/" if archive.getmember(m).isdir() else
                           m for m in archive.getnames()]

            if src != "" and src not in members:
                raise LbuildException("Archive has no file or folder called '{}'! "
                                      "Available files and folders are:\n  {}"
                                      .format(src, "\n  ".join(members)))

            def fn_isdir(path):
                return path.endswith("/") or path == ""

            def fn_listdir(path):
                depth = path.count("/")
                files = [m for m in members if m.startswith(path)]
                files = [m for m in files
                         if (m.count("/") <= depth) or (m.count("/") == depth + 1 and fn_isdir(m))]
                if depth:
                    files = ["/".join(m.split("/")[depth:]) for m in files]
                files = [m for m in files if len(m)]
                return files

            def fn_copy(srcpath, destpath):
                with tempfile.TemporaryDirectory() as tempdir:
                    archive.extract(srcpath, tempdir)
                    shutil.copy2(os.path.join(tempdir, srcpath), destpath)

            def log_copy(src, dest, operation_time):
                self.__buildlog.log(self.__module,
                                    os.path.join(archive_path, src), dest, operation_time, metadata)

            if fn_isdir(src):
                _copytree(log_copy, src, destpath, wrap_ignore,
                          fn_listdir, fn_isdir, fn_copy)
            else:
                if not os.path.exists(os.path.dirname(destpath)):
                    os.makedirs(os.path.dirname(destpath), exist_ok=True)
                _copyfile(src, destpath, fn_copy)

                endtime = time.time()
                total = endtime - starttime
                log_copy(src, destpath, total)

    def copy(self, src, dest=None, ignore=None, metadata=None):
        """
        Copy file or directory from the modulepath to the buildpath.

        If src or dest is a relative path it will be relocated to the
        module/buildpath. Absolute paths are not changed.

        If dest is empty the same name as src is used (relocated to
        the output path).
        """

        def wrap_ignore(path, files):
            ignored = lbuild.utils.ignore_patterns(*self.__module._ignore_patterns)(path, files)
            ignored.add(self.__module._filename)
            if ignore:
                ignored |= set(ignore(path, files))
            return ignored

        if dest is None:
            dest = src

        starttime = time.time()

        srcpath = os.path.normpath(src if os.path.isabs(src) else self.modulepath(src))
        destpath = os.path.normpath(dest if os.path.isabs(dest) else self.outpath(dest))

        srcrelpath = os.path.relpath(srcpath, self.__repopath)
        if srcrelpath.startswith(".."):
            raise LbuildException("Cannot access files outside of the repository!\n"
                                  "'{}'".format(srcrelpath))

        def log_copy(src, dest, operation_time):
            self.__buildlog.log(self.__module, src, dest, operation_time, metadata)

        if os.path.isdir(srcpath):
            _copytree(log_copy,
                      srcpath,
                      destpath,
                      wrap_ignore)
        else:
            if not os.path.exists(os.path.dirname(destpath)):
                os.makedirs(os.path.dirname(destpath), exist_ok=True)
            _copyfile(srcpath, destpath)

            endtime = time.time()
            total = endtime - starttime
            log_copy(srcpath, destpath, total)

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
                return os.path.normpath(path).replace('\\', '/')

        environment = RelEnvironment(loader=jinja2.FileSystemLoader(self.__repopath),
                                     extensions=['jinja2.ext.do'],
                                     undefined=jinja2.StrictUndefined)

        environment.filters.update(self.__module._filters)
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

    def template(self, src, dest=None, substitutions=None, filters=None, metadata=None):
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
            raise LbuildException("Cannot access template outside of repository!\n"
                                  "'{}'".format(src))

        if substitutions is None:
            substitutions = {}

        substitutions.update(self.substitutions)
        try:
            if filters is not None:
                # Reload environment if it uses different filters than
                # the previous environment
                self.__reload_template_environment(filters)

            template = self.template_environment.get_template(
                src.replace('\\', '/'),
                globals=self.__template_global_substitutions)

            output = template.render(substitutions)
        except jinja2.TemplateNotFound as error:
            raise LbuildException('Failed to retrieve Template: %s' % error)
        except (jinja2.exceptions.TemplateAssertionError,
                jinja2.exceptions.TemplateSyntaxError) as error:
            raise LbuildException("Error in template '{}:{}':\n"
                                  " {}: {}".format(error.filename,
                                                   error.lineno,
                                                   error.__class__.__name__,
                                                   error))
        except jinja2.exceptions.UndefinedError as error:
            raise LbuildTemplateException("Error in template '{}':\n"
                                          " {}: {}".format(self.modulepath(src),
                                                           error.__class__.__name__,
                                                           error))
        except LbuildException as error:
            raise LbuildException("Error in template '{}': \n"
                                  "{}".format(self.modulepath(src), error))
        except Exception as error:
            raise LbuildForwardException("Error in template '{}': \n"
                                         "{}".format(self.modulepath(src), error),
                                         error)

        outfile_name = self.outpath(dest)

        # Create folder structure if it doesn't exists
        if not SIMULATE:
            if not os.path.exists(os.path.dirname(outfile_name)):
                os.makedirs(os.path.dirname(outfile_name), exist_ok=True)

            with open(outfile_name, 'w', encoding="utf-8") as outfile:
                outfile.write(output)

        endtime = time.time()
        total = endtime - starttime
        self.__buildlog.log(self.__module, self.modulepath(src), outfile_name, total, metadata)

    def modulepath(self, *path):
        """Relocate given path to the path of the module file."""
        return os.path.join(self.__modulepath, *path)

    def repopath(self, *path):
        """Relocate given path to the path of the repo file."""
        return os.path.relpath(self.modulepath(*path), self.__repopath)

    def outpath(self, *path, basepath=None):
        """Relocate given path to the output path."""
        if basepath is None:
            basepath = self.outbasepath
        if basepath is None:
            return os.path.join(self.__outpath, *path)

        return os.path.join(self.__outpath, basepath, *path)

    def reloutpath(self, path, relative=None):
        if relative is None:
            relative = self.__outpath
        else:
            relative = os.path.join(self.__outpath, relative)
        path = os.path.join(self.__outpath, path)
        return os.path.relpath(path, relative)

    def generated_local_files(self, filterfunc=None):
        """
        Get all files which have been generated by this module and its
        submodules so far.

        Keyword arguments:
        filterfunc -- Function which is called to determine whether a path
            should be added to the output. If the function returns `True`
            the path is added.
        """
        filenames = []
        operations = self.__buildlog.operations_per_module(self.__module.fullname)
        for operation in operations:
            filename = os.path.normpath(
                os.path.join(os.path.relpath(os.path.dirname(operation.filename_out),
                                             self.outpath('.')),
                             os.path.basename(operation.filename_out)))
            if filterfunc is None or filterfunc(filename):
                filenames.append(filename)
        return filenames

    def add_metadata(self, key, *values):
        """
        Append additional information to the build log which can be used in the
        post-build step to generate additional files/data.
        """
        self.__buildlog.add_metadata(self.__module, key, values)

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)
