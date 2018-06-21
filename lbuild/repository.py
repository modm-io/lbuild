#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import glob
import logging
import fnmatch

import lbuild.option
import lbuild.filter
import lbuild.utils

from .exception import BlobException
from . import utils

LOGGER = logging.getLogger('lbuild.repository')


class RelocatePath:

    def __init__(self, basepath):
        self.basepath = basepath

    def __call__(self, *args):
        return os.path.join(self.basepath, *args)


class LocalFileReader:

    def __init__(self, basepath, filename):
        self.basepath = basepath
        self.filename = filename

    def read(self):
        with open(os.path.join(self.basepath, self.filename)) as file:
            return file.read()


class LocalFileReaderFactory:

    def __init__(self, basepath):
        self.basepath = basepath

    def __call__(self, filename):
        return LocalFileReader(self.basepath, filename)


class OptionNameResolver:
    """
    Option name resolver for repository options.
    """

    def __init__(self, repository, options):
        """

        Args:
            repository: Default repository. This name is used when the repository
                name is left empty (e.g. ":option").
            options:
        """
        self.repository = repository
        self.options = options

    def __getitem__(self, key):
        parts = key.split(":")
        if len(parts) != 2:
            raise BlobException("Option name '%s' must contain exactly one "
                                "colon to separate repository and option name.")
        repo, option = parts
        if repo == "":
            key = "%s:%s" % (self.repository.name, option)

        try:
            return self.options[key].value
        except KeyError:
            raise BlobException("Unknown option name '{}'".format(key))

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)


class RepositoryFacade:
    """
    External access to the repository.

    Used when execution the repository files.
    """

    def __init__(self, repository):
        self.__repository = repository

    @property
    def name(self):
        return self.__repository.name

    @name.setter
    def name(self, value):
        self.__repository.name = value

    @property
    def description(self):
        return self.__repository.description

    @description.setter
    def description(self, value):
        self.__repository.description = value

    def add_option(self, option: lbuild.option.Option):
        """
        Define new repository wide option.

        These options can be used by modules to decide whether they are
        available and what options they provide for a specific set of
        repository options.
        """
        option.repository = self.__repository
        option.module = None

        self.__repository.add_unique_option(option)

    def glob(self, pattern):
        pattern = os.path.abspath(self.__repository.relocate_relative_path(pattern))
        return glob.glob(pattern)

    def find_modules_recursive(self, basepath="", modulefile="module.lb", ignore=[]):
        """
        Find all module files following a specific pattern.

        Args:
            basepath: Rootpath for the search.
            modulefile: Filename pattern of the module files to search
                for (default: "module.lb").
            ignore: Filename pattern to ignore during search
        """
        ignore = utils.listify(ignore)
        basepath = self.__repository.relocate_relative_path(basepath)
        for path, _, files in os.walk(basepath):
            for file in files:
                if any(fnmatch.fnmatch(file, i) for i in ignore):
                    continue
                if fnmatch.fnmatch(file, modulefile):
                    modulefilepath = os.path.normpath(os.path.join(path, file))
                    self.__repository.module_files.append(modulefilepath)

    def add_modules(self, modules):
        """
        Add one or more module files.

        Args:
            modules: List of filenames
        """
        module_files = utils.listify(modules)

        for file in module_files:
            file = self.__repository.relocate_relative_path(file)

            if not os.path.isfile(file):
                raise BlobException("Module file not found '%s'" % file)

            self.__repository.module_files.append(file)


class Repository:
    """
    A repository is a set of modules.
    """

    def __init__(self, path, name=None):
        """
        Construct a new repository object.

        At the construction time of the object, the name of repository may not
        be known e.g. if the repository is loaded from a `repo.lb` file.
        """
        # Path to the repository file. All relative paths refer to this path.
        self.path = path
        self.name = name

        self.functions = None

        # List of module filenames which are later transfered into
        # module objects
        self.module_files = []

        # List of available module objects (modules that returned True in
        # the `prepare` step).
        self.modules = {}

        # Name -> Option()
        self.options = {}

    def relocate_relative_path(self, path):
        """
        Relocate relative paths to the path of the repository
        configuration file.
        """
        if not os.path.isabs(path):
            path = os.path.join(self.path, path)
        return os.path.normpath(path)

    def add_unique_option(self, option):
        """
        Add a new repository option.

        Raises an exception if the option is already defined for the repository.
        """
        if option.name in self.options:
            raise BlobException("Option name '%s' is already defined" % option.name)
        self.options[option.name] = option

    @staticmethod
    def get_global_functions(local, required, optional=None):
        """
        Get global functions from the environment.

        Args:
            required: List of required functions.
            optional: List of optional functions.
        """
        functions = {}
        for functionname in required:
            function = local.get(functionname)
            if function is None:
                raise BlobException("No function '{}' found!".format(functionname))
            functions[functionname] = function

        if optional is not None:
            for functionname in optional:
                function = local.get(functionname)
                functions[functionname] = function

        return functions

    @staticmethod
    def parse_repository(repofilename: str):
        LOGGER.debug("Parse repository '%s'", repofilename)

        repopath = os.path.dirname(os.path.realpath(repofilename))
        repo = Repository(repopath)
        try:
            local = {
                # The localpath(...) function can be used to create
                # a local path form the folder of the repository file.
                'localpath': RelocatePath(repopath),
                'FileReader': LocalFileReaderFactory(repopath),
                'listify': lbuild.filter.listify,

                'StringOption': lbuild.option.Option,
                'BooleanOption': lbuild.option.BooleanOption,
                'NumericOption': lbuild.option.NumericOption,
                'EnumerationOption': lbuild.option.EnumerationOption,
            }

            local = lbuild.utils.with_forward_exception(repo,
                    lambda: lbuild.utils.load_module_from_file(repofilename, local))
            repo.functions = Repository.get_global_functions(local, ['init', 'prepare'])

            # Execution init() function. In this function options are added.
            lbuild.utils.with_forward_exception(repo,
                    lambda: repo.functions['init'](RepositoryFacade(repo)))

            if repo.name is None:
                raise BlobException("The init(repo) function must set a repository name! "
                                    "Please write the 'name' attribute.")
        except FileNotFoundError as error:
            raise BlobException("Repository configuration file not found '{}'.".format(repofilename))
        except KeyError as error:
            raise BlobException("Invalid repository configuration file '{}':\n"
                                " {}: {}".format(repofilename,
                                                 error.__class__.__name__,
                                                 error))
        return repo

    def prepare_repository(self, options):
        lbuild.utils.with_forward_exception(self,
                lambda: self.functions["prepare"](RepositoryFacade(self),
                                                  OptionNameResolver(self,
                                                                     options)))

        modules = {}
        # Parse the modules inside this repository
        for modulefile in self.module_files:
            module = lbuild.module.Module.parse_module_file(self, modulefile)
            modules.update(module.prepare(options))
        return modules

    def remove_modules_without_parent(self):
        for name, module in self.modules.items():
            print(name, module.parent)

    def __lt__(self, other):
        return self.name.__cmp__(other.name)

    def __repr__(self):
        return "Repository({})".format(self.path)

    def __str__(self):
        """ Get string representation of repository.  """
        if self.name is not None:
            # The name must not always be set, e.g. during load
            # the repository name is only known after calling the
            # init function.
            return "{} at {}".format(self.name, self.path)
        else:
            return self.path
