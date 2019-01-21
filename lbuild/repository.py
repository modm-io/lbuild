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

import lbuild.utils

from .facade import RepositoryInitFacade, RepositoryPrepareFacade
from .node import BaseNode
from .exception import LbuildException

LOGGER = logging.getLogger('lbuild.repository')


class Repository(BaseNode):
    """
    A repository is a set of modules.
    """

    def __init__(self, filename, name=None):
        """
        Construct a new repository object.

        At the construction time of the object, the name of repository may not
        be known e.g. if the repository is loaded from a `repo.lb` file.
        """
        BaseNode.__init__(self, name, self.Type.REPOSITORY, self)
        # Path to the repository file. All relative paths refer to this path.
        self._filename = os.path.realpath(filename)
        self._config_map = {}
        self._new_filters = {}

        # List of module filenames which are later transfered into
        # module objects
        self._module_files = []
        # List of programatically added modules
        self._submodules = []

    @property
    def modules(self):
        return {m.fullname:m for m in self.all_modules()}

    @staticmethod
    def parse_repository(repofilename: str):
        LOGGER.debug("Parse repository '%s'", repofilename)

        repo = Repository(repofilename)
        repo._functions = lbuild.node.load_functions_from_file(
            repo,
            repofilename,
            required=['init', 'prepare'],
            optional=['build'])

        # Execution init() function. In this function options are added.
        repo._functions['init'](RepositoryInitFacade(repo))

        if repo.name is None:
            raise LbuildException("The init(repo) function must set a repository name! "
                                  "Please write the 'name' attribute.")

        # Prefix the global filters with the `repo.` name
        for name, func in repo._new_filters.items():
            repo._filters[repo.name + "." + name] = func

        # Prefix the global configuration map with the `repo:` name
        config_map = repo._config_map.copy()
        repo._config_map = {}
        for name, path in config_map.items():
            repo._config_map[repo.name + ":" + name] = path

        return repo

    def prepare(self):
        lbuild.utils.with_forward_exception(
            self,
            lambda: self._functions["prepare"](RepositoryPrepareFacade(self),
                                               self.option_value_resolver))

        modules = []
        # Parse the module files inside this repository
        for modulefile in self._module_files:
            module = lbuild.module.load_module_from_file(repository=self,
                                                         filename=modulefile,
                                                         parent=self.fullname)
            modules.extend(module)
        # Parse the module objects inside the repo file
        for module in self._submodules:
            module = lbuild.module.load_module_from_object(repository=self,
                                                           module_obj=module,
                                                           filename=self._filename,
                                                           parent=self.fullname)
            modules.extend(module)

        return modules

    def build(self, env):
        build = self._functions.get("build", None)
        if build is not None:
            lbuild.utils.with_forward_exception(self, lambda: build(env))

    def add_modules_recursive(self, basepath="", modulefile="module.lb", ignore=None):
        """
        Find all module files following a specific pattern.

        Args:
            basepath: Rootpath for the search.
            modulefile: Filename pattern of the module files to search
                for (default: "module.lb").
            ignore: Filename pattern to ignore during search
        """
        ignore = lbuild.utils.listify(ignore) + self._ignore_patterns
        ignore.append(os.path.relpath(self._filename, self._filepath))
        basepath = self._relocate_relative_path(basepath)
        for path, _, files in os.walk(basepath):
            for file in files:
                if any(fnmatch.fnmatch(file, i) for i in ignore):
                    continue
                if fnmatch.fnmatch(file, modulefile):
                    modulefilepath = os.path.normpath(os.path.join(path, file))
                    self._module_files.append(modulefilepath)

    def add_modules(self, *modules):
        """
        Add one or more module files.

        Args:
            modules: List of filenames
        """
        modules = [lbuild.utils.listify(m) for m in modules]
        modules = [inner for outer in modules for inner in outer]
        for module in modules:
            if isinstance(module, lbuild.module.ModuleBase):
                self._submodules.append(module)
            else:
                module = self._relocate_relative_path(module)
                if not os.path.isfile(module):
                    raise LbuildException("Module file not found '%s'" % module)
                self._module_files.append(module)

    def glob(self, pattern):
        pattern = os.path.abspath(self._relocate_relative_path(pattern))
        return glob.glob(pattern)

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __repr__(self):
        return "Repository({})".format(self._filepath)

    def __str__(self):
        """ Get string representation of repository.  """
        if self.name is not None:
            # The name must not always be set, e.g. during load
            # the repository name is only known after calling the
            # init function.
            return "{} at {}".format(self.name, self._filepath)

        return self._filepath
