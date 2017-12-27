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
import io
import sys
import unittest

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild


class RepositoryTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "resources", "repository", filename)

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def test_should_generate_exception_on_import_error(self):
        with self.assertRaises(lbuild.exception.BlobForwardException) as cm:
            self.parser.parse_repository(self._get_path("invalid_import.lb"))

        self.assertEqual(ModuleNotFoundError, cm.exception.exception.__class__)


if __name__ == '__main__':
    unittest.main()
