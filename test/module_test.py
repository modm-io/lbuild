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

import lbuild
from lbuild.option import *


class ModuleTest(unittest.TestCase):

    def setUp(self):
        self.repo = lbuild.repository.Repository(".")
        self.repo.name = "repo1"

        module = lbuild.module.ModuleInit(self.repo, "./module.lb")
        module.name = "other"
        module.available = True
        self.module, = lbuild.module.build_modules([module])

        self.repo.add_child(Option("target", "", default="hosted"))
        self.repo.add_child(NumericOption("foo", "", default=43))

        self.module.add_child(NumericOption("foo", "", default=456))
        self.module.add_child(NumericOption("bar", "", default=768))
        self.module.add_child(BooleanOption("xyz", "", default="Yes"))
        self.module.add_child(Option("abc", "", default="Hello World!"))

    def test_resolver_should_reject_invalid_names(self):
        resolver = self.module.module_resolver

        with self.assertRaises(lbuild.exception.LbuildException):
            resolver["value"]

        with self.assertRaises(lbuild.exception.LbuildException):
            resolver[":::value"]

    def test_resolver_should_reject_unknown_names(self):
        resolver = self.module.module_resolver

        with self.assertRaises(lbuild.exception.LbuildException):
            resolver["::value"]

    def test_resolver_should_resolve_option_names(self):

        resolver = self.repo.option_value_resolver
        self.assertEqual("hosted", resolver[':target'])
        self.assertEqual(43, resolver['repo1:foo'])

        resolver = self.module.option_value_resolver
        self.assertEqual(456, resolver["repo1:other:foo"])
        self.assertEqual(768, resolver["repo1::bar"])
        self.assertEqual(True, resolver[":other:xyz"])
        self.assertEqual("Hello World!", resolver["::abc"])

    def test_should_create_correct_representation(self):
        resolver = self.module.option_value_resolver
        self.assertEqual(4, repr(resolver).count("Option("))
        self.assertEqual(4, len(resolver))


if __name__ == '__main__':
    unittest.main()
