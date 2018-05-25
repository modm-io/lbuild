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

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))
from os.path import join

import lbuild
from lbuild.config import ConfigNode


class ConfigTest(unittest.TestCase):

    def _get_path(self, filename):
        return join(os.path.dirname(os.path.realpath(__file__)),
                    "resources", "config", filename)

    def _find_config(self, startpath=None, **kw):
        if startpath: startpath = self._get_path(startpath);
        config = ConfigNode.from_filesystem(startpath, **kw)
        return config.flatten() if config else config

    def _parse_config(self, filename):
        return ConfigNode.from_file(self._get_path(filename)).flatten()

    def test_should_parse_system_configuration_file(self):
        config = self._find_config(".")
        self.assertNotEqual(config, None)
        self.assertEqual(1, len(config.modules))
        self.assertIn(":module1", config.modules)
        self.assertIn(self._get_path("repo1.lb"), config.repositories)

        config = self._find_config("configfile/")
        self.assertNotEqual(config, None)
        self.assertEqual(1, len(config.modules))
        self.assertIn(":module1", config.modules)
        self.assertIn(self._get_path("repo1.lb"), config.repositories)

        config = self._find_config("configfile/", name="television_rules_the_nation.xml")
        self.assertEqual(config, None)

    def test_should_parse_configuration_file(self):
        config = self._parse_config("configfile/project.xml")

        modules = config.modules
        self.assertEqual(4, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        self.assertIn("::submodule3:subsubmodule1", modules)
        self.assertIn("::submodule3", modules)

        self.assertEqual(7, len(config.options))
        self.assertEqual(config.options[':target'], 'hosted')
        self.assertEqual(config.options['repo1:foo'], '43')

        self.assertEqual(config.options['repo1:other:foo'], '456')
        self.assertEqual(config.options['repo1::bar'], '768')
        self.assertEqual(config.options[':other:xyz'], 'No')
        self.assertEqual(config.options['::abc'], 'Hello World!')
        self.assertEqual(config.options['::submodule3::price'], '15')

    def test_should_parse_base_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_0.xml")

        self.assertEqual(1, len(config.repositories))
        self.assertIn(self._get_path("configfile_inheritance/repo3.lb"), config.repositories)

        self.assertEqual(2, len(config.options))
        self.assertEqual(config.options[":other:xyz"], "No")
        self.assertEqual(config.options["::abc"], "Hello World!")

        self.assertEqual(1, len(config.modules))
        self.assertIn("repo1:other", config.modules)

    def test_should_inherit_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_1a.xml")

        self.assertEqual(2, len(config.repositories))
        self.assertIn(self._get_path("configfile_inheritance/repo1.lb"), config.repositories)
        self.assertIn(self._get_path("configfile_inheritance/repo3.lb"), config.repositories)

        self.assertEqual(5, len(config.options))
        self.assertEqual(config.options[":other:xyz"], "No")
        self.assertEqual(config.options["::abc"], "Hello World!")
        self.assertEqual(config.options["repo1:foo"], "43")
        self.assertEqual(config.options["repo1:other:foo"], "456")
        self.assertEqual(config.options["repo1::bar"], "768")

        self.assertEqual(2, len(config.modules))
        self.assertIn("repo1:other", config.modules)
        self.assertIn(":module1", config.modules)

    def test_should_recursive_inherit_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_2.xml")


        self.assertEqual(2, len(config.repositories))
        self.assertIn(self._get_path("configfile_inheritance/repo1.lb"), config.repositories)
        self.assertIn(self._get_path("configfile_inheritance/repo3.lb"), config.repositories)

        self.assertEqual(6, len(config.options))
        self.assertEqual(config.options[":other:xyz"], "No")
        self.assertEqual(config.options["::abc"], "Hello World!")

        self.assertEqual(config.options["repo1:other:foo"], "456")
        self.assertEqual(config.options["repo1::bar"], "768")

        self.assertEqual(config.options[":target"], "hosted")
        self.assertEqual(config.options["repo1:foo"], "42")

        self.assertEqual(3, len(config.modules))
        self.assertIn("repo1:other", config.modules)
        self.assertIn(":module1", config.modules)
        self.assertIn("::submodule3:subsubmodule2", config.modules)

    def test_should_recursive_inherit_from_multiple_bases_configuration(self):
        config = self._parse_config("configfile_inheritance/depth_2_multiple.xml")

        self.assertEqual(3, len(config.repositories))
        self.assertIn(self._get_path("configfile_inheritance/repo1.lb"), config.repositories)
        self.assertIn(self._get_path("configfile_inheritance/repo2.lb"), config.repositories)
        self.assertIn(self._get_path("configfile_inheritance/repo3.lb"), config.repositories)

        self.assertEqual(7, len(config.options))
        self.assertEqual(config.options["repo1:other:foo"], "456")
        self.assertEqual(config.options["repo1::bar"], "768")

        self.assertEqual(config.options[":other:xyz"], "Yes")
        self.assertEqual(config.options["::abc"], "Hello World!")
        self.assertEqual(config.options["::submodule3::price"], "15")

        self.assertEqual(config.options[":target"], "hosted")
        self.assertEqual(config.options["repo1:foo"], "42")

        self.assertEqual(5, len(config.modules))
        self.assertIn("::submodule3:subsubmodule2", config.modules)
        self.assertIn("repo1:other", config.modules)
        self.assertIn(":module1", config.modules)
        self.assertIn("::submodule3:subsubmodule1", config.modules)
        self.assertIn("::submodule3", config.modules)

if __name__ == '__main__':
    unittest.main()
