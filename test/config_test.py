#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2017, Fabian Greif
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

from lbuild.config import Option


class ConfigTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "resources",
                            "config",
                            filename)

    def _parse_config(self, filename):
        return lbuild.config.Configuration.parse_configuration(self._get_path(filename))

    def test_should_parse_configuration_file(self):
        config = self._parse_config("configfile/project.xml")

        modules = config.selected_modules
        self.assertEqual(4, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        self.assertIn("::submodule3:subsubmodule1", modules)
        self.assertIn("::submodule3", modules)

        self.assertEqual(7, len(config.options))
        self.assertIn(Option(':target', 'hosted'), config.options)
        self.assertIn(Option('repo1:foo', '43'), config.options)

        self.assertIn(Option('repo1:other:foo', '456'), config.options)
        self.assertIn(Option('repo1::bar', '768'), config.options)
        self.assertIn(Option(':other:xyz', 'No'), config.options)
        self.assertIn(Option('::abc', 'Hello World!'), config.options)
        self.assertIn(Option('::submodule3::price', '15'), config.options)

    def test_should_parse_base_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_0.xml")

        self.assertEqual(1, len(config.repositories))
        self.assertIn(os.path.join(config.configpath, "repo3.lb"), config.repositories)

        self.assertEqual(2, len(config.options))
        self.assertIn(Option(":other:xyz", "No"), config.options)
        self.assertIn(Option("::abc", "Hello World!"), config.options)

        self.assertEqual(1, len(config.selected_modules))
        self.assertIn("repo1:other", config.selected_modules)

    def test_should_inherit_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_1a.xml")

        self.assertEqual(2, len(config.repositories))
        self.assertIn(os.path.join(config.configpath, "repo1.lb"), config.repositories)
        self.assertIn(os.path.join(config.configpath, "repo3.lb"), config.repositories)

        self.assertEqual(5, len(config.options))
        self.assertEqual(Option(":other:xyz", "No"), config.options[0])
        self.assertEqual(Option("::abc", "Hello World!"), config.options[1])
        self.assertEqual(Option("repo1:foo", "43"), config.options[2])
        self.assertEqual(Option("repo1:other:foo", "456"), config.options[3])
        self.assertEqual(Option("repo1::bar", "768"), config.options[4])

        self.assertEqual(2, len(config.selected_modules))
        self.assertIn("repo1:other", config.selected_modules)
        self.assertIn(":module1", config.selected_modules)

    def test_should_recursive_inherit_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_2.xml")

        self.assertEqual(2, len(config.repositories))
        self.assertIn(os.path.join(config.configpath, "repo1.lb"), config.repositories)
        self.assertIn(os.path.join(config.configpath, "repo3.lb"), config.repositories)

        self.assertEqual(6, len(config.options))
        self.assertEqual(Option(":other:xyz", "No"), config.options[0])
        self.assertEqual(Option("::abc", "Hello World!"), config.options[1])

        self.assertEqual(Option("repo1:other:foo", "456"), config.options[2])
        self.assertEqual(Option("repo1::bar", "768"), config.options[3])

        self.assertEqual(Option(":target", "hosted"), config.options[4])
        self.assertEqual(Option("repo1:foo", "42"), config.options[5])

        self.assertEqual(3, len(config.selected_modules))
        self.assertIn("repo1:other", config.selected_modules)
        self.assertIn(":module1", config.selected_modules)
        self.assertIn("::submodule3:subsubmodule2", config.selected_modules)

    def test_should_recursive_inherit_from_multiple_bases_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_2_multiple.xml")

        self.assertEqual(3, len(config.repositories))
        self.assertIn(os.path.join(config.configpath, "repo1.lb"), config.repositories)
        self.assertIn(os.path.join(config.configpath, "repo3.lb"), config.repositories)
        self.assertIn(os.path.join(config.configpath, "repo2.lb"), config.repositories)

        self.assertEqual(7, len(config.options))
        self.assertEqual(Option("repo1:other:foo", "456"), config.options[0])
        self.assertEqual(Option("repo1::bar", "768"), config.options[1])

        self.assertEqual(Option(":other:xyz", "Yes"), config.options[2])
        self.assertEqual(Option("::abc", "Hello World!"), config.options[3])
        self.assertEqual(Option("::submodule3::price", "15"), config.options[4])

        self.assertEqual(Option(":target", "hosted"), config.options[5])
        self.assertEqual(Option("repo1:foo", "42"), config.options[6])

        self.assertEqual(5, len(config.selected_modules))
        self.assertIn("::submodule3:subsubmodule2", config.selected_modules)
        self.assertIn("repo1:other", config.selected_modules)
        self.assertIn(":module1", config.selected_modules)
        self.assertIn("::submodule3:subsubmodule1", config.selected_modules)
        self.assertIn("::submodule3", config.selected_modules)

if __name__ == '__main__':
    unittest.main()
