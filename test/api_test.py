#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2017, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import unittest
import testfixtures
from pathlib import Path

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.exception as le


class ApiTest(unittest.TestCase):

    def _rel_path(self, path):
        return os.path.relpath(self._get_path(path), os.getcwd())

    def _get_path(self, path):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", path)

    def _assert_config(self, api, **kw):
        defaults = {
            "filename": Path(),
            "options": dict(),
            "modules": list(),
            "repositories": list(),
            "vcs": list(),
            "cachefolder": Path(),
        }
        defaults.update(kw)
        for key, default in defaults.items():
            self.assertEqual(getattr(api.config, key), default)

    def test_empty_builder(self):
        api = lbuild.api.Builder()
        self.assertEqual(api.cwd, os.getcwd())
        self._assert_config(api)

        api = lbuild.api.Builder(config="project.xml")
        self._assert_config(api)

    def test_config_builder(self):
        api = lbuild.api.Builder(config=self._get_path("parser/api/simple.xml"))
        self.assertEqual(api.cwd, self._get_path("parser/api"))
        self._assert_config(api,
            filename=self._rel_path("parser/api/simple.xml"),
            options={"repo:option": ("value", self._get_path("parser/api/simple.xml")),
                     "repo:module:option": ("value", self._get_path("parser/api/simple.xml"))},
            modules=["repo:module"],
            repositories=[self._get_path("parser/api/repo.lb")],
            cachefolder=self._rel_path("parser/api/.lbuild_cache"))

    def test_lbuild_config_builder(self):
        api = lbuild.api.Builder(cwd=self._get_path("config"))
        self.assertEqual(api.cwd, self._get_path("config"))
        self._assert_config(api,
            filename=self._rel_path("config/lbuild.xml"),
            options={":target": ("hosted", self._get_path("config/lbuild.xml"))},
            modules=[":module1"],
            repositories=[self._get_path("config/repo1.lb")],
            cachefolder=self._rel_path("config/.lbuild_cache"))

    def test_project_config_builder(self):
        api = lbuild.api.Builder(cwd=self._get_path("parser/api"), config="project.xml")
        self.assertEqual(api.cwd, self._get_path("parser/api"))
        self._assert_config(api,
            filename=self._rel_path("parser/api/project.xml"),
            options={"repo:option": ("value", self._get_path("parser/api/project.xml"))},
            modules=["repo:module"],
            repositories=[self._get_path("parser/api/repo.lb")],
            cachefolder=self._rel_path("parser/api/.lbuild_cache"))

    def test_command_line_config_builder(self):
        api = lbuild.api.Builder(config="repo:config")
        self.assertEqual(api.cwd, os.getcwd())
        self._assert_config(api,
            filename="command-line",
            _extends={"command-line": ["repo:config"]})


if __name__ == '__main__':
    unittest.main()
