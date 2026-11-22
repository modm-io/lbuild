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

        self.config = Configuration("config", "", "path.xml")
        self.config._selected = True
        self.repo.add_child(self.config)
        self.config2 = Configuration("config2", "",
                {"v1": "version1.xml", "v2": "version2.xml"},
                default="v2")
        self.repo.add_child(self.config2)

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

        resolver = self.repo.config_resolver
        self.assertEqual(self.config, resolver["repo1:config"])
        self.assertEqual(self.config2, resolver["repo1:config2"])


class AliasRedirectTest(unittest.TestCase):

    def setUp(self):
        self.parser = lbuild.parser.Parser()
        repoinit = lbuild.repository.RepositoryInit(None, ".")
        repoinit.name = "repo"
        self.repo = lbuild.repository.Repository(repoinit)
        self.repo.parent = self.parser

        inits = []
        for parent, name in (("repo", "new"), ("repo:new", "sub")):
            init = lbuild.module.ModuleInit(self.repo, "./module.lb")
            init.parent, init.name, init.available = parent, name, True
            inits.append(init)
        self.new, self.sub = lbuild.module.build_modules(inits)
        self.sub.add_child(NumericOption("opt", "", default=42))

        self.repo.add_child(Alias("old", "Use new.", destination=":new"))
        self.repo.add_child(Alias("older", "Use old.", destination=":old"))
        self.repo.add_child(Alias("missing", "Gone.", destination=":nope"))
        self.repo.add_child(Alias("removed", "Removed."))

    def test_should_redirect_option_below_alias(self):
        with self.assertLogs("lbuild.node", "WARNING"):
            resolver = self.sub.option_value_resolver
            self.assertEqual(42, resolver["repo:old:sub:opt"])
            self.assertEqual(42, resolver[":old:sub:opt"])

    def test_should_redirect_module_below_alias(self):
        with self.assertLogs("lbuild.node", "WARNING"):
            self.assertEqual(self.sub, self.new.module_resolver["repo:old:sub"])

    def test_should_redirect_through_alias_chain(self):
        with self.assertLogs("lbuild.node", "WARNING") as logs:
            self.assertEqual(self.sub, self.new.module_resolver["repo:older:sub"])
        self.assertEqual(2, len(logs.output))

    def test_should_warn_once_per_alias(self):
        with self.assertLogs("lbuild.node", "WARNING") as logs:
            resolver = self.sub.option_value_resolver
            resolver["repo:old:sub:opt"]
            resolver["repo:old:sub:opt"]
            self.new.module_resolver["repo:old:sub"]
        self.assertEqual(1, len(logs.output))
        self.assertIn("Use new.", logs.output[0])

    def test_should_not_redirect_below_removed_alias(self):
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.new.module_resolver["repo:removed:sub"]

    def test_should_not_redirect_other_repository(self):
        repoinit = lbuild.repository.RepositoryInit(None, ".")
        repoinit.name = "repo"
        repo = lbuild.repository.Repository(repoinit)
        repo.add_child(Alias("old", "", destination=":new"))
        self.assertEqual("other:old:sub", repo._redirect_alias("other:old:sub"))

    def test_contains_should_be_false_for_unusable_destination(self):
        logging.disable(logging.WARNING)
        resolver = self.new.module_resolver
        self.assertNotIn("repo:missing", resolver)
        self.assertIsNone(resolver.get("repo:missing"))
        self.assertIn("repo:old", resolver)

        self.new._selected = False
        self.assertNotIn("repo:old", resolver)
        self.assertIsNone(resolver.get("repo:old"))
        logging.disable(logging.NOTSET)

    def test_should_raise_for_unusable_destination(self):
        logging.disable(logging.WARNING)
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.new.module_resolver["repo:missing"]
        self.new._selected = False
        with self.assertRaises(le.LbuildResolverSearchException):
            self.repo.module_resolver["repo:old"]
        logging.disable(logging.NOTSET)

    def test_find_modules_should_follow_alias(self):
        with self.assertLogs("lbuild.node", "WARNING"):
            self.assertEqual([self.new], self.parser.find_modules("repo:old"))
            self.assertEqual([self.new], self.parser.find_modules("repo:older"))
            self.assertEqual([self.sub], self.parser.find_modules("repo:old:sub"))

    def test_find_modules_should_select_unselected_destination(self):
        logging.disable(logging.WARNING)
        self.new._selected = False
        self.assertEqual([self.new], self.parser.find_modules("repo:old"))
        logging.disable(logging.NOTSET)

    def test_find_modules_should_raise_for_missing_destination(self):
        logging.disable(logging.WARNING)
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.parser.find_modules("repo:missing")
        logging.disable(logging.NOTSET)

    def test_find_modules_wildcard_should_skip_missing_destination(self):
        logging.disable(logging.WARNING)
        self.assertEqual([self.new], self.parser.find_modules("repo:*"))
        self.assertCountEqual([self.new, self.sub], self.parser.find_modules("repo:old:**"))
        logging.disable(logging.NOTSET)

    def test_find_any_without_types_should_keep_alias(self):
        nodes = self.parser.find_any("repo:old")
        self.assertEqual(1, len(nodes))
        self.assertEqual(Alias, type(nodes[0]))


if __name__ == '__main__':
    unittest.main()
