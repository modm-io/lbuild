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
    
    def test_resolverShouldRejectInvalidNames(self):
        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, {}, {})
        
        with self.assertRaises(lbuild.exception.BlobException):
            resolver["value"]
        
        with self.assertRaises(lbuild.exception.BlobException):
            resolver[":::value"]
    
    def test_resolverShouldRejectUnknownNames(self):
        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, {}, {})
        
        with self.assertRaises(lbuild.exception.BlobException):
            resolver["::value"]
    
    def test_resolverShouldResolveOptionNames(self):
        repo_options = {
            "repo1:target": lbuild.environment.Option("target", "", "hosted"),
            "repo1:foo": lbuild.environment.NumericOption("foo", "", 43),
        }
        
        module_options = {
            "repo1:other:foo": lbuild.environment.NumericOption("foo", "", 456),
            "repo1:other:bar": lbuild.environment.NumericOption("bar", "", 768),
            "repo1:other:xyz": lbuild.environment.BooleanOption("bar", "", "Yes"),
            "repo1:other:abc": lbuild.environment.Option("abc", "", "Hello World!"),
        }
        
        resolver = lbuild.module.OptionNameResolver(self.repo, self.module, repo_options, module_options)
        
        self.assertEqual("hosted", resolver[':target'])
        self.assertEqual(43, resolver['repo1:foo'])
        
        self.assertEqual(456, resolver["repo1:other:foo"])
        self.assertEqual(768, resolver["repo1::bar"])
        self.assertEqual(True, resolver[":other:xyz"])
        self.assertEqual("Hello World!", resolver["::abc"])

    def test_shouldCreateCorrectRepresentation(self):
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
