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
import enum
import unittest
import re

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild.option
from lbuild.repository import Repository
from lbuild.module import Module


class OptionTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repository("path", name="repo")
        module = lbuild.module.ModuleInit(self.repo, "filename")
        module.name = "module"
        module.available = True
        self.module = lbuild.module.build_modules([module])[0]
        lbuild.format.plain = True

    def test_should_provide_string_representation_for_base_option(self):
        option = lbuild.option.Option("test", "description", "value")

        output = option.description
        self.assertTrue(output.startswith(">> test"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_with_repo(self):
        option = lbuild.option.Option("test", "description", "value")
        self.repo.add_option(option)

        output = option.description
        self.assertTrue(output.startswith(">> repo:test"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_full(self):
        option = lbuild.option.Option("test", "description", "value")
        self.module.add_option(option)

        output = option.description
        self.assertTrue(output.startswith(">> repo:module:test"))
        self.assertTrue("value" in output)

    def test_should_provide_short_description(self):
        option = lbuild.option.Option("test", "first paragraph\n\nsecond paragraph", "value")
        self.assertEqual("first paragraph", option.short_description)

    def test_should_provide_factsheet(self):
        option = lbuild.option.Option("test", "long description", "value")
        output = option.description

        self.assertIn("test", output, "Option name")
        self.assertIn("Value: value", output)
        self.assertIn("Inputs: [String]", output)
        self.assertIn("long description", output)

    def test_should_provide_factsheet_without_value(self):
        option = lbuild.option.Option("test", "long description")
        output = option.description

        self.assertIn("test", output, "Option name")
        self.assertIn("Value: REQUIRED", output)
        self.assertIn("Inputs: [String]", output)
        self.assertIn("long description", output)

    def test_should_be_constructable_from_boolean(self):
        option = lbuild.option.BooleanOption("test",
                                             "description",
                                             False)
        self.assertEqual(False, option.value)
        option.value = 1
        self.assertEqual(True, option.value)
        option.value = 'yes'
        self.assertEqual(True, option.value)
        option.value = 'no'
        self.assertEqual(False, option.value)
        option.value = 'True'
        self.assertEqual(True, option.value)
        option.value = False
        self.assertEqual(False, option.value)

    def test_should_be_constructable_from_number(self):
        option = lbuild.option.NumericOption("test",
                                             "description",
                                             minimum=0,
                                             maximum=100,
                                             default=1)
        self.assertEqual(1, option.value)
        option.value = 2
        self.assertEqual(2, option.value)
        option.value = "3"
        self.assertEqual(3, option.value)

        def set_below():
            option.value = -1
        def set_above():
            option.value = 1000
        def set_text():
            option.value = "hello"

        self.assertRaises(lbuild.exception.LbuildException, set_below)
        self.assertRaises(lbuild.exception.LbuildException, set_above)
        self.assertRaises(lbuild.exception.LbuildException, set_text)

        self.assertRaises(lbuild.exception.LbuildException,
                          lambda: lbuild.option.NumericOption("test", "description",
                                                              minimum=0, maximum=0))
        self.assertRaises(lbuild.exception.LbuildException,
                          lambda: lbuild.option.NumericOption("test", "description",
                                                              minimum=100, maximum=-100))
        self.assertRaises(lbuild.exception.LbuildException,
                          lambda: lbuild.option.NumericOption("test", "description",
                                                              minimum=-10, maximum=-100))

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

    def test_should_format_boolean_option(self):
        option = lbuild.option.BooleanOption("test",
                                             "description",
                                             default=True)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("True in [True, False]", output, "Output")

    def test_should_format_numeric_option(self):
        def construct(minimum=None, maximum=None, default=None):
            option = lbuild.option.NumericOption("test", "description", minimum, maximum, default)
            return str(lbuild.format.format_option_value_description(option))

        self.assertIn("REQUIRED in [-Inf ... +Inf]", construct())
        self.assertIn("REQUIRED in [-1 ... +Inf]",   construct(minimum=-1))
        self.assertIn("REQUIRED in [-Inf ... -1]",   construct(maximum=-1))
        self.assertIn("0 in [-Inf .. 0 .. +Inf]",    construct(default=0))
        self.assertIn("0 in [0 ... +Inf]",           construct(minimum=0, default=0))
        self.assertIn("0 in [-Inf ... 0]",           construct(maximum=0, default=0))
        self.assertIn("1 in [0 .. 1 .. 100]",        construct(minimum=0, maximum=100, default=1))
        self.assertIn("1 in [-100 .. -1 .. -10]",    construct(minimum=-100, maximum=-10, default=-1))

    def test_should_format_enumeration_option(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 default="value1",
                                                 enumeration=enum_list)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("value1 in [value1, value2]", output, "Output")

    def test_should_format_enumeration_option_set(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.SetOption("test",
                                         "description",
                                         default=["value1", "value2"],
                                         enumeration=enum_list)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("{value1, value2} in [value1, value2]", output)

    def test_should_format_enumeration_option_without_default_value(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 enumeration=enum_list)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("REQUIRED in [value1, value2]", output)

if __name__ == '__main__':
    unittest.main()
