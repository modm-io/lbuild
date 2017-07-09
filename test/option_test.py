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

    def test_should_provide_short_description(self):
        option = lbuild.option.Option("test", "first paragraph\n\nsecond paragraph", "value")
        self.assertEqual("first paragraph", option.short_description)

    def test_should_provide_factsheet(self):
        option = lbuild.option.Option("test", "long description", "value")
        output = option.factsheet()

        self.assertIn("test", output, "Option name")
        self.assertIn("Current value: value", output)
        self.assertIn("Possible values: String", output)
        self.assertIn("long description", output)

    def test_should_provide_factsheet_without_value(self):
        option = lbuild.option.Option("test", "long description")
        output = option.factsheet()

        self.assertIn("test", output, "Option name")
        self.assertNotIn("Current value:", output)
        self.assertIn("Possible values: String", output)
        self.assertIn("long description", output)

    def test_should_be_constructable_from_enum(self):
        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default=TestEnum.value1,
                                                 enumeration=TestEnum)
        self.assertEqual(1, option.value)

    def test_should_be_constructable_from_enum_set(self):
        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=[TestEnum.value1, TestEnum.value2],
                                         enumeration=TestEnum)
        self.assertEqual([1, 2], option.value)

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

    def test_should_be_constructable_from_dict_set(self):
        enum_dict = {
            "value1": 1,
            "value2": 2,
        }
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=["value1", "value2"],
                                         enumeration=enum_dict)
        self.assertEqual([1, 2], option.value)

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

    def test_should_be_constructable_from_list_set(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=["value1", "value2"],
                                         enumeration=enum_list)
        self.assertEqual(["value1", "value2"], option.value)

    def test_should_be_constructable_from_list_set_duplicates(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=["value1", "value1"],
                                         enumeration=enum_list)
        self.assertEqual(["value1"], option.value)

    def test_should_be_constructable_from_range(self):
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default=10,
                                                 enumeration=range(1, 21))
        self.assertEqual(10, option.value)

    def test_should_be_constructable_from_range_set(self):
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=range(5, 9),
                                         enumeration=range(1, 21))
        self.assertEqual([5,6,7,8], option.value)

    def test_should_be_constructable_from_set(self):
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default=10,
                                                 enumeration=set(range(1, 21)))
        self.assertEqual(10, option.value)

    def test_should_be_constructable_from_set_set(self):
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=set(range(5,9)),
                                         enumeration=set(range(1, 21)))
        self.assertEqual(set([5,6,7,8]), set(option.value))

    def test_should_format_enumeration_option(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default="value1",
                                                 enumeration=enum_list)

        output = option.format()
        self.assertIn("test = value1", output, "Current value")
        self.assertIn("[value1, value2]", output, "List of all available values")

    def test_should_format_enumeration_option_set(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=["value1", "value2"],
                                         enumeration=enum_list)

        output = option.format()
        self.assertIn("test = [value1, value2]", output, "Current value")
        self.assertIn("[value1, value2]", output, "List of all available values")

    def test_should_format_enumeration_option_without_default_value(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 enumeration=enum_list)

        output = option.format()
        self.assertNotIn("test = value1", output, "No current value")
        self.assertNotIn("test = value2", output, "No current value")
        self.assertIn("[value1, value2]", output, "List of all available values")

if __name__ == '__main__':
    unittest.main()
