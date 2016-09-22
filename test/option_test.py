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

class OptionTest(unittest.TestCase):

    def test_should_provide_string_representation_for_base_option(self):
        option = lbuild.option.Option("test", "description", "value")
        self.assertEqual("test = value", str(option))

    def test_should_be_constructable_from_enum(self):
        class TestEnum(enum.Enum):
            value1 = 1
            value2 = 2

        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 value=TestEnum.value1,
                                                 enumeration=TestEnum)
        self.assertEqual("value1", option.value.name)
        self.assertEqual(1, option.value.value)

    def test_should_be_constructable_from_dict(self):
        enum_dict = {
            "value1": 1,
            "value2": 2,
        }
        option = lbuild.option.EnumerationOption("test",
                                                 "description",
                                                 value="value1",
                                                 enumeration=enum_dict)
        self.assertEqual("value1", option.value.name)
        self.assertEqual(1, option.value.value)

if __name__ == '__main__':
    unittest.main()
