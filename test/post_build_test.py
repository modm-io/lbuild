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

    def _configure_and_build_library(self, configfile, outpath, cmd_options=[]):
        configuration = lbuild.config.ConfigNode.from_file(configfile)
        configuration.add_commandline_options(cmd_options)
        self.parser._config_flat = configuration

        self.parser.merge_repository_options()
        modules = self.parser.prepare_repositories()

        module_options = self.parser.merge_module_options()
        selected_modules = self.parser.find_modules(self.parser.config.modules)
        build_modules = self.parser.resolve_dependencies(selected_modules)

        log = lbuild.buildlog.BuildLog(str(outpath))
        self.parser.build_modules(build_modules, log)
        return log

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    @testfixtures.tempdir()
    def test_should_execute_pre_and_post_build_functions(self, tempdir):
        self.parser.parse_repository(self._get_path("repo.lb"))

        stdout_file = io.StringIO()
        with contextlib.redirect_stdout(stdout_file):
            # Build library
            self._configure_and_build_library(self._get_path("config.xml"),
                                              outpath=tempdir)

        output = stdout_file.getvalue()
        self.assertIn("Validate", output)
        self.assertIn("Post-Build", output)

    @testfixtures.tempdir()
    def test_should_abort_after_validate_functions(self, tempdir):
        self.parser.parse_repository(self._get_path("repo.lb"))

        stdout_file = io.StringIO()
        with contextlib.redirect_stdout(stdout_file):
            # Build library
            cmd_options = ["repo:module:fail=True"]

            self.assertRaises(lbuild.exception.LbuildAggregateException, lambda:
                              self._configure_and_build_library(self._get_path("config.xml"),
                                                                outpath=tempdir,
                                                                cmd_options=cmd_options))

        output = stdout_file.getvalue()
        self.assertIn("Validate", output)
        self.assertNotIn("Post-Build", output)

    @testfixtures.tempdir()
    def test_should_contain_metadata(self, tempdir):
        self.parser.parse_repository(self._get_path("repo.lb"))

        stdout_file = io.StringIO()
        with contextlib.redirect_stdout(stdout_file):
            # Build library
            buildlog = self._configure_and_build_library(self._get_path("config.xml"),
                                                         outpath=tempdir)

        self.assertEqual(3, len(buildlog.metadata["include_path"]))
        self.assertEqual(2, len(buildlog.metadata["required_libraries"]))

        self.assertIn("test", buildlog.metadata["required_libraries"])
        self.assertIn("test2", buildlog.metadata["required_libraries"])

if __name__ == '__main__':
    unittest.main()
