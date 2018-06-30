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


class DepedencyBuilderTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "dependency_builder", filename)

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def prepare_arguments(self, commands):
        """
        Prepare the command-line arguments.

        Adds the path to the generated config file.
        """
        argument_parser = lbuild.main.prepare_argument_parser()
        commandline_arguments = ["-c{}".format(self._get_path("config.xml")), ]
        commandline_arguments.extend(commands)
        args = argument_parser.parse_args(commandline_arguments)
        return args

    def test_should_create_dependency_graph(self):
        args = self.prepare_arguments(["dependencies", ])
        output = lbuild.main.run(args)
        self.assertIsNotNone(output)

        self.assertIn("repo_module2 -> repo_module1;", output)
        self.assertIn("repo_module2_submodule0 -> repo_module2;", output)
        self.assertIn("repo_module2_submodule1 -> repo_module2;", output)
        self.assertIn("repo_module2_submodule2 -> repo_module2;", output)
        self.assertIn("repo_module2_submodule3 -> repo_module2;", output)
        self.assertIn("repo_module2_submodule4 -> repo_module2;", output)

    def test_should_create_dependency_graph_for_selection(self):
        args = self.prepare_arguments(["dependencies", "-mrepo:module2:submodule0"])
        output = lbuild.main.run(args)
        self.assertIsNotNone(output)

        self.assertIn("repo_module2 -> repo_module1;", output)
        self.assertIn("repo_module2_submodule0 -> repo_module2;", output)

    def test_should_create_dependency_graph_for_selection_with_limited_length(self):
        args = self.prepare_arguments(["dependencies", "-mrepo:module2:submodule0", "-n1"])
        output = lbuild.main.run(args)
        self.assertIsNotNone(output)

        self.assertIn("repo_module2_submodule0 -> repo_module2;", output)

if __name__ == '__main__':
    unittest.main()
