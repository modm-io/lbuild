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


class ConfigTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "config", filename)

    def test_should_parse_configuration_file(self):
        config = lbuild.config.Configuration.parse_configuration(self._get_path("configfile/project.xml"))

        modules = config.selected_modules
        self.assertEqual(4, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        self.assertIn("::submodule3:subsubmodule1", modules)
        self.assertIn("::submodule3", modules)

        self.assertEqual(7, len(config.options))
        self.assertIn(lbuild.config.Option(':target', 'hosted'), config.options)
        self.assertIn(lbuild.config.Option('repo1:foo', '43'), config.options)

        self.assertIn(lbuild.config.Option('repo1:other:foo', '456'), config.options)
        self.assertIn(lbuild.config.Option('repo1::bar', '768'), config.options)
        self.assertIn(lbuild.config.Option(':other:xyz', 'No'), config.options)
        self.assertIn(lbuild.config.Option('::abc', 'Hello World!'), config.options)
        self.assertIn(lbuild.config.Option('::submodule3::price', '15'), config.options)



if __name__ == '__main__':
    unittest.main()
