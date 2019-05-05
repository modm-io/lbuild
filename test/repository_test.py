#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017, Fabian Greif
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

class RepositoryTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "resources", "repository", filename)

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def test_should_generate_exception_on_import_error(self):
        with self.assertRaises(le.LbuildForwardException) as cm:
            self.parser.parse_repository(self._get_path("invalid_import.lb"))

        self.assertTrue(issubclass(cm.exception.exception.__class__, ImportError))

    def test_should_not_load_non_existant_repository_file(self):
        with self.assertRaises(le.LbuildParserAddRepositoryNotFoundException):
            self.parser.parse_repository(self._get_path("non_existant.lb"))

    def test_should_not_load_invalid_repository(self):
        with self.assertRaises(le.LbuildRepositoryNoNameException):
            self.parser.parse_repository(self._get_path("no_name.lb"))

        with self.assertRaises(le.LbuildConfigAddNotFoundException):
            self.parser.parse_repository(self._get_path("no_config.lb"))

        with self.assertRaises(le.LbuildRepositoryDuplicateChildException):
            self.parser.parse_repository(self._get_path("duplicate_child.lb"))

        self.parser.parse_repository(self._get_path("ok_repo.lb"))
        with self.assertRaises(le.LbuildParserRepositoryEmptyException):
            self.parser.prepare_repositories()

        with self.assertRaises(le.LbuildRepositoryAddModuleNotFoundException):
            repo = self.parser.parse_repository(self._get_path("no_module.lb"))
            repo.prepare()

    def test_should_not_load_invalid_repository2(self):
        with self.assertRaises(le.LbuildRepositoryAddModuleRecursiveNotFoundException):
            repo = self.parser.parse_repository(self._get_path("no_module_recursive.lb"))
            repo.prepare()


if __name__ == '__main__':
    unittest.main()
