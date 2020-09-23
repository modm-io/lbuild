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

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

from lbuild.option import *
from lbuild.repository import Repository
import lbuild.exception as le


class OptionTest(unittest.TestCase):

    def setUp(self):
        repoinit = lbuild.repository.RepositoryInit(None, "path")
        repoinit.name = "repo"
        self.repo = lbuild.repository.Repository(repoinit)


        module = lbuild.module.ModuleInit(self.repo, "filename")
        module.parent = self.repo.name
        module.name = "module"
        module.available = True

        self.module = lbuild.module.build_modules([module])[0]

        # Disable advanced formatting for a console and use the plain output
        lbuild.format.PLAIN = True

    def test_should_provide_string_representation_for_base_option(self):
        option = Option("test", "description", "value")

        output = option.description
        self.assertTrue(output.startswith(">> test  [Option]"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_with_repo(self):
        option = Option("test", "description", "value")
        self.repo.add_child(option)

        output = option.description
        self.assertTrue(output.startswith(">> repo:test  [Option]"))
        self.assertTrue("value" in output)

    def test_should_provide_string_representation_for_base_option_full(self):
        option = Option("test", "description", "value")
        self.module.add_child(option)

        output = option.description
        self.assertTrue(output.startswith(">> repo:module:test  [Option]"))
        self.assertTrue("value" in output)

    def test_should_provide_short_description(self):
        option = Option("test", "first paragraph\n\nsecond paragraph", "value")
        self.assertEqual("first paragraph", option.short_description)

    def test_should_provide_factsheet(self):
        option = Option("test", "long description", "value")
        output = option.description

        self.assertIn("test  [Option]", output)
        self.assertIn("Value: value", output)
        self.assertIn("Inputs: [String]", output)
        self.assertIn("long description", output)

    def test_should_provide_factsheet_without_value(self):
        option = Option("test", "long description")
        output = option.description

        self.assertIn("test  [Option]", output)
        self.assertIn("Value: REQUIRED", output)
        self.assertIn("Inputs: [String]", output)
        self.assertIn("long description", output)

    def test_should_be_constructable_from_string(self):
        option = StringOption("test", "description", default="hello")
        self.assertIn("test  [StringOption]", option.description)
        self.assertEqual("hello", option.value)
        option.value = "world"
        self.assertEqual("world", option.value)
        option.value = 1
        self.assertEqual("1", option.value)
        option.value = None
        self.assertEqual("None", option.value)
        option.value = False
        self.assertEqual("False", option.value)

        def validate_string(value):
            if not isinstance(value, str):
                raise TypeError("must be of type str")
            if "magic" not in value:
                raise ValueError("magic not in value")

        option = StringOption("test", "description", default="magic",
                              validate=validate_string)
        self.assertEqual("magic", option.value)
        option.value = "magic word"
        self.assertEqual("magic word", option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "hello"

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = 1

        with self.assertRaises(le.LbuildOptionInputException):
            StringOption("test", "description", default="hello",
                         validate=validate_string)

    def test_should_be_constructable_from_path(self):
        option = PathOption("test", "description", default="filename.txt")
        self.assertIn("test  [PathOption]", option.description)
        self.assertEqual("filename.txt", option.value)
        option.value = "filename.txt.in"
        self.assertEqual("filename.txt.in", option.value)
        option.value = "path/filename.txt"
        self.assertEqual("path/filename.txt", option.value)
        option.value = "path/folder"
        self.assertEqual("path/folder", option.value)
        option.value = "path/folder/"
        self.assertEqual("path/folder/", option.value)
        option.value = "/path/folder/"
        self.assertEqual("/path/folder/", option.value)
        option.value = "/"
        self.assertEqual("/", option.value)
        option.value = "\tfile \n  "
        self.assertEqual("file", option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = ""
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "//"
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "/folder//"
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "//folder/"

        option = PathOption("test", "description", default="", empty_ok=True)
        self.assertEqual("", option.value)

        option = PathOption("test", "description", default="filename.txt", absolute=True)
        self.assertEqual("{}/filename.txt".format(os.getcwd()), option.value)
        option._filename = "/root/test/hello.lb"
        option.value = "filename.txt"
        self.assertEqual("/root/test/filename.txt", option.value)
        option.value = "/absolute/filename.txt"
        self.assertEqual("/absolute/filename.txt", option.value)

        option = PathOption("test", "description", default="", empty_ok=True, absolute=True)
        self.assertEqual("", option.value)
        option.value = ""
        self.assertEqual("", option.value)
        option.value = "filename.txt"
        self.assertEqual("{}/filename.txt".format(os.getcwd()), option.value)
        option._filename = "/root/test/hello.lb"
        option.value = "filename.txt"
        self.assertEqual("/root/test/filename.txt", option.value)
        option.value = "/absolute/filename.txt"
        self.assertEqual("/absolute/filename.txt", option.value)

    def test_should_be_constructable_from_boolean(self):
        option = BooleanOption("test", "description", False)
        self.assertIn("test  [BooleanOption]", option.description)
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

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "hello"

    def test_should_be_constructable_from_number(self):
        option = NumericOption("test", "description", default=1,
                               minimum=0, maximum=100)
        self.assertIn("test  [NumericOption]", option.description)
        self.assertEqual(1, option.value)
        option.value = 2
        self.assertEqual(2, option.value)
        option.value = "3"
        self.assertEqual(3, option.value)
        option.value = 4.5
        self.assertEqual(4.5, option.value)
        option.value = str(6.7)
        self.assertEqual(6.7, option.value)
        option.value = "2**6"
        self.assertEqual(2**6, option.value)
        option.value = "(30 + 30/2) * 4 - 100 # inline comment" # eval()
        self.assertEqual(80, option.value)
        option.value = "{'key1': 23, 'key2': 42*2}['key2']" # eval()
        self.assertEqual(42*2, option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = -1
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = 1000
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "hello"

        with self.assertRaises(le.LbuildOptionConstructionException):
            NumericOption("test", "description", minimum=0, maximum=0)
        with self.assertRaises(le.LbuildOptionConstructionException):
            NumericOption("test", "description", minimum=100, maximum=-100)
        with self.assertRaises(le.LbuildOptionConstructionException):
            NumericOption("test", "description", minimum=-10, maximum=-100)
        with self.assertRaises(le.LbuildOptionConstructionException):
            NumericOption("test", "description", minimum="str")
        with self.assertRaises(le.LbuildOptionConstructionException):
            NumericOption("test", "description", maximum="str")

    def test_should_be_constructable_from_enum(self):

        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = EnumerationOption("test", "description",
                                   default=TestEnum.value1,
                                   enumeration=TestEnum)
        self.assertIn("test  [EnumerationOption]", option.description)
        self.assertEqual(1, option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = 1
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "hello"

    def test_should_be_constructable_from_enum_set(self):

        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=TestEnum),
                    default=[TestEnum.value1, TestEnum.value2])
        self.assertIn("test  [EnumerationSetOption]", option.description)
        self.assertEqual([1, 2], option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = 1
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = {TestEnum.value1, 1}

    def test_should_be_constructable_from_dict(self):
        enum_dict = {
            "value1": 1,
            "value2": 2,
        }
        option = EnumerationOption("test", "description",
                                   default="value1",
                                   enumeration=enum_dict)
        self.assertEqual(1, option.value)

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = 1
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "value3"

    def test_should_be_constructable_from_dict_set(self):
        enum_dict = {
            "value1": 1,
            "value2": 2,
        }
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=enum_dict),
                    default=["value1", "value2"])
        self.assertEqual([1, 2], option.value)
        self.assertIn("{value1, value2}",
                      str(lbuild.format.format_option_value_description(option)))

        with self.assertRaises(le.LbuildOptionInputException):
            option.value = {1, 2}
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "value3"

    def test_should_be_constructable_from_list(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = EnumerationOption("test", "description",
                                   default="value1",
                                   enumeration=enum_list)
        self.assertEqual("value1", option.value)
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = "value3"

    def test_should_be_constructable_from_list_set(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=enum_list),
                    default=["value1", "value2"])
        self.assertIn("{value1, value2}",
                      str(lbuild.format.format_option_value_description(option)))
        self.assertEqual(["value1", "value2"], option.value)
        with self.assertRaises(le.LbuildOptionInputException):
            option.value = {"value3"}

    def test_should_be_constructable_from_list_set_duplicates(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=enum_list),
                    default=["value1", "value1"])
        self.assertEqual(["value1"], option.value)
        self.assertIn("{value1}",
                      str(lbuild.format.format_option_value_description(option)))

        option1 = OptionSet(
                    EnumerationOption("test", "description", enumeration=enum_list),
                    default=["value1", "value1"], unique=False)
        self.assertEqual(["value1", "value1"], option1.value)
        self.assertIn("[value1, value1]",
                      str(lbuild.format.format_option_value_description(option1)))

    def test_should_be_constructable_from_range(self):
        option = EnumerationOption("test", "description",
                                   default=10,
                                   enumeration=range(1, 21))
        self.assertEqual(10, option.value)

    def test_should_be_constructable_from_range_set(self):
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=range(1, 21)),
                    default=range(5, 9))
        self.assertEqual([5, 6, 7, 8], option.value)
        self.assertIn("{5, 6, 7, 8}",
                      str(lbuild.format.format_option_value_description(option)))

    def test_should_be_constructable_from_set(self):
        option = EnumerationOption("test", "description",
                                   default=10,
                                   enumeration=set(range(1, 21)))
        self.assertEqual(10, option.value)

    def test_should_be_constructable_from_set_set(self):
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=set(range(1, 21))),
                    default=set(range(5, 9)))
        self.assertEqual({5, 6, 7, 8}, set(option.value))
        self.assertIn("{5, 6, 7, 8}",
                      str(lbuild.format.format_option_value_description(option)))

    def test_should_format_boolean_option(self):
        option = BooleanOption("test", "description", default=True)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("True in [True, False]", output, "Output")

    def test_should_format_numeric_option(self):

        def construct(minimum=None, maximum=None, default=None, value=None):
            option = NumericOption("test", "description", minimum, maximum, default)
            if value is not None: option.value = value;
            return str(lbuild.format.format_option_value_description(option))

        self.assertIn("REQUIRED in [-Inf ... +Inf]", construct())
        self.assertIn("REQUIRED in [-1 ... +Inf]", construct(minimum=-1))
        self.assertIn("REQUIRED in [-Inf ... -1]", construct(maximum=-1))
        self.assertIn("0 in [-Inf .. 0 .. +Inf]", construct(default=0))
        self.assertIn("0 in [0 ... +Inf]", construct(minimum=0, default=0))
        self.assertIn("0 in [-Inf ... 0]", construct(maximum=0, default=0))
        self.assertIn("1 in [0 .. 1 .. 100]", construct(minimum=0, maximum=100, default=1))
        self.assertIn("-1 in [-100 .. -1 .. -10]", construct(minimum=-100, maximum=-10, default=-1))

        self.assertIn("2*30 (60) in [0*0 .. 2*30 .. 200*2]",
                      construct(minimum="0*0", maximum="200*2", default="2*30"))
        self.assertIn("3*60 (180) in [0*0 .. 2*30 .. 200*2]",
                      construct(minimum="0*0", maximum="200*2", default="2*30", value="3*60"))

    def test_should_format_enumeration_option(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = EnumerationOption("test", "description",
                                   default="value1",
                                   enumeration=enum_list)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("value1 in [value1, value2]", output, "Output")

    def test_should_format_enumeration_option_set_empty(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = OptionSet(
                    EnumerationOption("test", "description", enumeration=enum_list))

        self.assertEqual([], option.value)
        self.assertIn("{} in [value1, value2]",
                      str(lbuild.format.format_option_value_description(option)))

    def test_should_format_enumeration_option_without_default_value(self):
        enum_list = [
            "value1",
            "value2",
        ]
        option = EnumerationOption("test", "description",
                                   enumeration=enum_list)

        output = str(lbuild.format.format_option_value_description(option))
        self.assertIn("REQUIRED in [value1, value2]", output)


if __name__ == '__main__':
    unittest.main()
