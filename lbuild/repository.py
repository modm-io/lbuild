#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import glob

import lbuild.option

from .exception import BlobException
from . import utils


class OptionNameResolver:
    """
    Option name resolver for repository options.
    """
    def __init__(self, repository, options):
        """

        Keyword arguments:
        repository -- Default repository. This name is used when the repository
            name is left empty (e.g. ":option").
        options --
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
            raise BlobException("Unknown option name '%s'" % key)

    def __repr__(self):
        return repr(self.options)

    def __len__(self):
        return len(self.options)


class Repository:
    """
    A repository is a set of modules.
    """
    def __init__(self, path, name=None):
        # Path to the repository file. All relative paths refer to this path.
        self.path = path
        self.name = name

        self.functions = None

        # Dict of modules, using the filename as the key
        self.modules = {}

        # Name -> Option()
        self.options = {}

    def _relocate(self, path):
        """
        Relocate relative paths to the path of the repository
        configuration file.
        """
        if not os.path.isabs(path):
            path = os.path.join(self.path, path)
        return os.path.normpath(path)

    def glob(self, pattern):
        pattern = os.path.abspath(self._relocate(pattern))
        return glob.glob(pattern)

    def add_modules(self, modules):
        """
        Add one or more module files.

        Args:
            modules: List of filenames
        """
        module_files = utils.listify(modules)

        for file in module_files:
            file = self._relocate(file)

            if not os.path.isfile(file):
                raise BlobException("Module file not found '%s'" % file)

            self.modules[file] = None

    def find_modules(self, basepath="", modulefile="module.lb"):
        """
        Find all module files following a specific pattern.

        Args:
            basepath   : Rootpath for the search.
            modulefile : Filename of the module files to search
                for (default: "module.lb").
        """
        basepath = self._relocate(basepath)
        for path, _, files in os.walk(basepath):
            if modulefile in files:
                modulepath = os.path.normpath(os.path.join(path, modulefile))
                self.modules[modulepath] = None

    def add_option(self, option: lbuild.option.Option):
        """
        Define new repository wide option.

        These options can be used by modules to decide whether they are
        available and what options they provide for a specific set of
        repository options.
        """
        self._check_for_duplicates(option.name)
        option.repository = self
        option.module = None
        self.options[option.name] = option

    def _check_for_duplicates(self, name):
        if name in self.options:
            raise BlobException("Option name '%s' is already defined" % name)

    def __lt__(self, other):
        return self.name.__cmp__(other.name)

