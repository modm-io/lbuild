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
import unittest

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild


class ModuleTest(unittest.TestCase):

    def setUp(self):
        self.repo = lbuild.repository.Repository(".")
        self.repo.name = "repo1"

        self.module = lbuild.module.Module(self.repo, "module.lb", ".")
        self.module.name = "other"
        self.module.register_module()

    def test_resolver_should_reject_invalid_names(self):
        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, {}, {})

        with self.assertRaises(lbuild.exception.BlobException):
            resolver["value"]

        with self.assertRaises(lbuild.exception.BlobException):
            resolver[":::value"]

    def test_resolver_should_reject_unknown_names(self):
        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, {}, {})

        with self.assertRaises(lbuild.exception.BlobException):
            resolver["::value"]

    def test_resolver_should_resolve_option_names(self):
        repo_options = {
            "repo1:target": lbuild.option.Option("target", "", default="hosted"),
            "repo1:foo": lbuild.option.NumericOption("foo", "", default=43),
        }

        module_options = {
            "repo1:other:foo": lbuild.option.NumericOption("foo", "", default=456),
            "repo1:other:bar": lbuild.option.NumericOption("bar", "", default=768),
            "repo1:other:xyz": lbuild.option.BooleanOption("bar", "", default="Yes"),
            "repo1:other:bla:abc": lbuild.option.Option("abc", "", default="Hello World!"),
        }

        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, repo_options, module_options)

        self.assertEqual("hosted", resolver[':target'])
        self.assertEqual(43, resolver['repo1:foo'])

        self.assertEqual(456, resolver["repo1:other:foo"])
        self.assertEqual(768, resolver["repo1::bar"])
        self.assertEqual(True, resolver[":other:xyz"])
        self.assertEqual("Hello World!", resolver["::bla:abc"])

    def test_should_create_correct_representation(self):
        repo_options = {
            "repo1:target": None,
            "repo1:foo": None,
        }

        module_options = {
            "repo1:other:foo": None,
            "repo1:other:bar": None,
            "repo1:other:xyz": None,
            "repo1:other:abc": None,
        }

        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, repo_options, module_options)

        self.assertEqual(6, len(repr(resolver).split(",")))
        self.assertEqual(6, len(resolver))


if __name__ == '__main__':
    unittest.main()
