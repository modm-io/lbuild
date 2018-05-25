#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
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

import lbuild


class FilterTest(unittest.TestCase):

    def test_should_convert_string_to_list(self):
        obj = lbuild.filter.listify( None )
        self.assertEqual(obj, [])
        obj = lbuild.filter.listify( [] )
        self.assertEqual(obj, [])
        obj = lbuild.filter.listify( [0,1,2] )
        self.assertEqual(obj, [0,1,2])
        obj = lbuild.filter.listify( (0,1,2) )
        self.assertEqual(obj, [0,1,2])
        obj = lbuild.filter.listify( set([0,1,2]) )
        self.assertEqual(obj, [0,1,2])
        lbuild.filter.listify( range(0,3) )
        self.assertEqual(obj, [0,1,2])
        obj = lbuild.filter.listify( reversed(range(0,3)) )
        self.assertEqual(obj, [2,1,0])
        obj = lbuild.filter.listify( "string" )
        self.assertEqual(obj, ["string"])
        obj = lbuild.filter.listify( ["string"] )
        self.assertEqual(obj, ["string"])

    def test_should_rewrap_text(self):
        text = lbuild.filter.wordwrap("This is a long text which can be re-wrapped.", 20)

        self.assertEqual("This is a long text\n"
                         "which can be re-\n"
                         "wrapped.", text)

    def test_should_indent_text_without_first_line(self):
        text = lbuild.filter.indent("This is a long text\n"
                                    "  which to be\n"
                                    "indented.", 3)

        self.assertEqual("This is a long text\n"
                         "     which to be\n"
                         "   indented.", text)

    def test_should_indent_text(self):
        text = lbuild.filter.indent("This is a long text\n"
                                    "  which to be\n"
                                    "indented.", 3, first_line=True)

        self.assertEqual("   This is a long text\n"
                         "     which to be\n"
                         "   indented.", text)

    def test_should_split_lines(self):
        parts = lbuild.filter.split("Hello", "l")
        self.assertEqual(["He", "", "o"], parts)

    def test_should_extract_values_by_key(self):
        dict1 = {"foo": 1, "bar": 2}
        dict2 = {1: 16, "foo": "Hello"}

        parts = lbuild.filter.values([dict1, dict2], "foo")
        self.assertEqual([1, "Hello"], parts)

    def test_should_pad(self):
        text = lbuild.filter.pad("Hello World", 20, tabwidth=4)

        self.assertEqual("Hello World\t\t\t", text)

if __name__ == '__main__':
    unittest.main()
