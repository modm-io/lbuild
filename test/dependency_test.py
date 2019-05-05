#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import unittest

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.exception as le


class DepedencyTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "dependency", filename)

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def test_should_collapse_mutiply_defined_dependencies(self):
        self.parser.parse_repository(self._get_path("multiple_dependencies/repo.lb"))
        self.parser.prepare_repositories()

        module = self.parser.find_module(":module2")

        self.assertEqual(1, len(module.dependencies))
        self.assertEqual("repo:module1", module.dependencies[0].fullname)

    def test_should_raise_unknown_dependency(self):
        self.parser.parse_repository(self._get_path("multiple_dependencies/repo.lb"))
        self.parser.prepare_repositories()

        module = self.parser.find_module(":module2")
        module.add_dependencies(":NOPE")

        with self.assertRaises(le.LbuildParserCannotResolveDependencyException):
            self.parser.resolve_dependencies([module])

    def test_should_update_option_dependencies(self):
        self.parser.parse_repository(self._get_path("option_dependency/repo.lb"))
        self.parser.prepare_repositories()
        self.parser.config.options[":module2:dependency"] = ":module1"
        self.parser.merge_module_options()

        module = self.parser.find_module(":module2")

        self.assertEqual(1, len(module.dependencies))
        self.assertEqual("repo:module1", module.dependencies[0].fullname)

if __name__ == '__main__':
    unittest.main()
