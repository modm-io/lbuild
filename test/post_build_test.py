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
import contextlib
import testfixtures

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild

class PostBuildTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "resources", "post_build", filename)

    def _parse_config(self, filename):
        return lbuild.config.Configuration.parse_configuration(self._get_path(filename))

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    @testfixtures.tempdir()
    def test_should_execute_pre_and_post_build_functions(self, tempdir):
        self.parser.parse_repository(self._get_path("repo.lb"))

        stdout_file = io.StringIO()
        with contextlib.redirect_stdout(stdout_file):
            # Build library
            self.parser.configure_and_build_library(self._get_path("config.xml"), tempdir)

        output = stdout_file.getvalue()
        self.assertIn("Pre-Build", output)
        self.assertIn("Post-Build", output)

if __name__ == '__main__':
    unittest.main()
