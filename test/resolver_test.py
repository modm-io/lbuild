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

import io, contextlib
import lbuild, logging
from lbuild.option import *
from lbuild.node import Alias
from lbuild.repository import Configuration
import lbuild.exception as le
import lbuild.module as lm

class ResolverTest(unittest.TestCase):

    def setUp(self):
        repoinit = lbuild.repository.RepositoryInit(None, ".")
        repoinit.name = "repo1"
        self.repo = lbuild.repository.Repository(repoinit)

        module = lbuild.module.ModuleInit(self.repo, "./module.lb")
        module.parent = self.repo.name
        module.name = "other"
        module.available = True
        self.module, = lbuild.module.build_modules([module])

        self.repo.add_child(Configuration("config", "", "path.xml"))
        self.repo.add_child(Configuration("config2", "",
                                          {"v1": "version1.xml", "v2": "version2.xml"},
                                          default="v2"))

        self.repo.add_child(Option("target", "", default="hosted"))
        self.repo.add_child(NumericOption("foo", "", default=43))
        self.repo.add_child(Alias("alias0", "", destination="foo"))

        self.module.add_child(NumericOption("foo", "", default=456))
        self.module.add_child(NumericOption("bar", "", default=768))
        self.module.add_child(BooleanOption("xyz", "", default="Yes"))
        self.module.add_child(Option("abc", "", default="Hello World!"))

        self.module.add_child(Alias("alias1", "", destination="foo"))
        self.module.add_child(Alias("alias2", "", destination="::bar"))
        self.module.add_child(Alias("alias3", "", destination=":other:xyz"))
        self.module.add_child(Alias("alias4", "", destination="repo1:other:abc"))

        self.module.add_child(Alias("alias_module", "", destination=":other"))

        self.module.add_child(Alias("alias_none", ""))
        self.module.add_child(Alias("alias_wrong", "::wrong"))


    def test_should_resolve_module(self):
        resolver = self.module.module_resolver
        self.assertEqual(self.module, resolver["repo1:other"])

    def test_resolver_should_reject_invalid_names(self):
        resolver = self.module.module_resolver

        with self.assertRaises(le.LbuildResolverException):
            resolver["value"]

        with self.assertRaises(le.LbuildResolverException):
            resolver[":::value"]

    def test_resolver_should_reject_unknown_names(self):
        resolver = self.module.module_resolver

        with self.assertRaises(le.LbuildResolverException):
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

    def test_should_resolve_alias(self):
        logging.disable(logging.WARNING)

        resolver = self.repo.option_value_resolver
        self.assertEqual(43, resolver[":alias0"])

        # Resolve Option aliases
        resolver = self.module.option_value_resolver
        self.assertEqual(456, resolver["repo1:other:alias1"])
        self.assertEqual(768, resolver["repo1:other:alias2"])
        self.assertEqual(True, resolver["repo1:other:alias3"])
        self.assertEqual("Hello World!", resolver["repo1:other:alias4"])
        # Resolve modules
        resolver = self.module.module_resolver
        self.assertEqual(self.module, resolver["repo1:other:alias_module"])

        with self.assertRaises(le.LbuildResolverAliasException):
            resolver["repo1:other:alias_none"]

        with self.assertRaises(le.LbuildResolverAliasException):
            resolver["repo1:other:alias_wrong"]

        logging.disable(logging.NOTSET)

    def test_should_resolve_config_value(self):
        resolver = self.module.option_value_resolver
        self.assertEqual("", resolver["repo1:config"])
        self.assertEqual("v2", resolver["repo1:config2"])


if __name__ == '__main__':
    unittest.main()
