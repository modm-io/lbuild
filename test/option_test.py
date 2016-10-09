#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import enum
import unittest

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild.option
from lbuild.repository import Repository
from lbuild.module import Module


class OptionTest(unittest.TestCase):

    def setUp(self):
        self.default_repository = Repository("path", name="repo")
        self.default_module = Module(self.default_repository, "filename", "path", name="module")
        self.default_module.register_module()

    def test_should_provide_string_representation_for_base_option(self):
        option = lbuild.option.Option("test", "description", "value")

        output = option.format()
        self.assertTrue(output.startswith("test"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_with_repo(self):
        option = lbuild.option.Option("test", "description", "value")
        option.repository = self.default_repository

        output = option.format()
        self.assertTrue(output.startswith("repo:test"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_full(self):
        option = lbuild.option.Option("test", "description", "value")
        option.repository = self.default_repository
        option.module = self.default_module

        output = option.format()
        self.assertTrue(output.startswith("repo:module:test"))
        self.assertTrue("value" in output)

    def test_should_be_constructable_from_enum(self):
        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default=TestEnum.value1,
                                                 enumeration=TestEnum)
        self.assertEqual(1, option.value)

    def test_should_be_constructable_from_dict(self):
        enum_dict = {
            "value1": 1,
            "value2": 2,
        }
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default="value1",
                                                 enumeration=enum_dict)
        self.assertEqual(1, option.value)

    def test_should_be_constructable_from_list(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default="value1",
                                                 enumeration=enum_list)
        self.assertEqual("value1", option.value)

if __name__ == '__main__':
    unittest.main()
