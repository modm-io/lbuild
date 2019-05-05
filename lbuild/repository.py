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

import lbuild.exception as le
import lbuild.facade as lf
from .node import BaseNode


LOGGER = logging.getLogger('lbuild.repository')


class Configuration(BaseNode):
    def __init__(self, name, path, description):
        BaseNode.__init__(self, name, BaseNode.Type.CONFIG)
        self._config = path
        if description is None:
            description = ""
        self._description = description


def load_repository_from_file(parser, filename):
    repo = RepositoryInit(parser, filename)
    try:
        repo._functions = lbuild.node.load_functions_from_file(
            repo, filename,
            required=['init', 'prepare'], optional=['build'])
    except FileNotFoundError as error:
        raise le.LbuildParserAddRepositoryNotFoundException(parser, filename)

    return repo.init()


class RepositoryInit:
    def __init__(self, parser, filename):
        self._filename = os.path.realpath(filename)
        self._filepath = os.path.dirname(self._filename) if filename else None
        self._functions = {}
        self._parser = parser

        self.name = None
        self.description = ""
        self._format_description = lbuild.format.format_description
        self._format_short_description = lbuild.format.format_short_description

        self._submodules = []
        self._options = []
        self._filters = []
        self._queries = []
        self._ignore_patterns = []
        self._configurations = []

    def init(self):
        lbuild.utils.with_forward_exception(self,
                lambda: self._functions['init'](lf.RepositoryInitFacade(self)))
        return Repository(self)


class Repository(BaseNode):
    """
    A repository is a set of modules.
    """

    def __init__(self, repo: RepositoryInit):
        """
        Construct a new repository object.

        At the construction time of the object, the name of repository may not
        be known e.g. if the repository is loaded from a `repo.lb` file.
        """
        BaseNode.__init__(self, repo.name, self.Type.REPOSITORY, self)

        self._filename = repo._filename
        self._description = repo.description
        self._functions = repo._functions
        self._format_description = repo._format_description
        self._format_short_description = repo._format_short_description

        if repo.name is None:
            raise le.LbuildRepositoryNoNameException(repo._parser, repo)

        self._ignore_patterns.extend(repo._ignore_patterns)
        # Prefix the global filters with the `repo.` name
        for (name, func) in repo._filters:
            if not name.startswith("{}.".format(self.name)):
                nname = "{}.{}".format(self.name, name)
                LOGGER.warning("Namespacing repository filter '{}' to '{}'!"
                               .format(name, nname))
                name = nname
            self._filters[name] = func

        try:
            for child in (repo._options + repo._queries):
                self.add_child(child)
            for (name, path, description) in repo._configurations:
                path = self._relocate_relative_path(path)
                if not os.path.isfile(path):
                    raise le.LbuildConfigAddNotFoundException(repo, path)
                self.add_child(Configuration(name, path, description))

        except le.LbuildNodeDuplicateChildException as error:
            raise le.LbuildRepositoryDuplicateChildException(repo._parser, repo, error)

        # List of module filenames which are later transfered into
        # module objects
        self._module_files = []
        # List of programatically added modules
        self._submodules = []

    @property
    def modules(self):
        return {m.fullname:m for m in self.all_modules()}

    def prepare(self):
        lbuild.utils.with_forward_exception(
            self,
            lambda: self._functions["prepare"](lf.RepositoryPrepareFacade(self),
                                               self.option_value_resolver))

        modules = []
        # Parse the module files inside this repository
        for modulefile in self._module_files:
            module = lbuild.module.load_module_from_file(repository=self,
                                                         filename=modulefile)
            modules.extend(module)
        # Parse the module objects inside the repo file
        for submodule in self._submodules:
            module = lbuild.module.load_module_from_object(repository=self,
                                                           module_obj=submodule,
                                                           filename=self._filename)
            modules.extend(module)

        return modules

    def build(self, env):
        build = self._functions.get("build", None)
        if build is not None:
            lbuild.utils.with_forward_exception(self, lambda: build(env.facade))

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
        found_one_module = False
        for path, _, files in os.walk(basepath):
            for file in files:
                if any(fnmatch.fnmatch(file, i) for i in ignore):
                    continue
                if fnmatch.fnmatch(file, modulefile):
                    modulefilepath = os.path.normpath(os.path.join(path, file))
                    self._module_files.append(modulefilepath)
                    found_one_module = True
        if not found_one_module:
            raise le.LbuildRepositoryAddModuleRecursiveNotFoundException(self, basepath)

    def add_modules(self, *modules):
        """
        Add one or more module files.

        Args:
            modules: List of filenames
        """
        modules = [lbuild.utils.listify(m) for m in modules]
        modules = [inner for outer in modules for inner in outer]
        for module in modules:
            if isinstance(module, str):
                module = self._relocate_relative_path(module)
                if not os.path.isfile(module):
                    raise le.LbuildRepositoryAddModuleNotFoundException(self, module)
                self._module_files.append(module)
            else:
                self._submodules.append(module)

    def glob(self, pattern):
        pattern = os.path.abspath(self._relocate_relative_path(pattern))
        return glob.glob(pattern)

    def __repr__(self):
        return "Repository({})".format(self._filepath)
