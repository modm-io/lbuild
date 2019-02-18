#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2019, Niklas Hauser
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

import lbuild.query
from lbuild.repository import Repository


class QueryTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repository("path", name="repo")
        module = lbuild.module.ModuleInit(self.repo, "filename")
        module.name = "module"
        module.available = True
        self.module = lbuild.module.build_modules([module])[0]
        self.env = "environment"

        # Disable advanced formatting for a console and use the plain output
        lbuild.format.PLAIN = True

    def method(self, arg):
        """
        method docstring
        """
        return arg

    def test_should_construct_function(self):
        def local_function():
            """
            local docstring
            """
            pass

        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.Query(function=int())
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.Query(function=2)
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.Query(function=lambda: None)
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.Query(function=lambda arg: arg)

        query = lbuild.query.Query(function=local_function)
        self.assertEqual("local_function", query.name)
        self.assertTrue(query.description.startswith(">> local_function()"))
        self.assertIn("local docstring", query.description)

        query = lbuild.query.Query(name="different", function=local_function)
        self.assertEqual("different", query.name)
        self.assertTrue(query.description.startswith(">> different()"))
        self.assertIn("local docstring", query.description)

        query = lbuild.query.Query(function=self.method)
        self.assertEqual("method", query.name)
        self.assertTrue(query.description.startswith(">> method(arg)"))
        self.assertIn("method docstring", query.description)

        query = lbuild.query.Query(name="different", function=self.method)
        self.assertEqual("different", query.name)
        self.assertTrue(query.description.startswith(">> different(arg)"))
        self.assertIn("method docstring", query.description)

        query = lbuild.query.Query(name="lambda_name", function=lambda: None)
        self.assertEqual("lambda_name", query.name)
        self.assertTrue(query.description.startswith(">> lambda_name()"))

        query = lbuild.query.Query(name="lambda_name", function=lambda arg, arg2: None)
        self.assertEqual("lambda_name", query.name)
        self.assertTrue(query.description.startswith(">> lambda_name(arg, arg2)"))

    def test_should_construct_property(self):
        def local_factory():
            """
            local docstring
            """
            pass

        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.EnvironmentQuery(factory=int())
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.EnvironmentQuery(factory=2)
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.EnvironmentQuery(factory=lambda: None)
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.EnvironmentQuery(factory=lambda arg: arg)
        with self.assertRaises(lbuild.exception.LbuildException):
            query = lbuild.query.EnvironmentQuery(factory=local_factory)

        query = lbuild.query.EnvironmentQuery(factory=self.method)
        self.assertEqual("method", query.name)
        self.assertTrue(query.description.startswith(">> method"))
        self.assertIn("method docstring", query.description)

    def test_should_call_function(self):
        local_called = 0

        def local_factory(arg):
            nonlocal local_called
            local_called += 1
            return arg

        query = lbuild.query.Query(function=local_factory)
        retval = query.value(self.env)("arg")
        self.assertEqual("arg", retval)
        self.assertEqual(1, local_called)

        retval = query.value(self.env)("arg2")
        self.assertEqual("arg2", retval)
        self.assertEqual(2, local_called)

    def test_should_call_property(self):
        factory_called = 0

        def local_factory(env):
            nonlocal factory_called
            factory_called += 1
            return env

        query = lbuild.query.EnvironmentQuery(factory=local_factory)
        retval = query.value(self.env)
        self.assertEqual(self.env, retval)
        self.assertEqual(1, factory_called)

        retval = query.value(self.env)
        self.assertEqual(self.env, retval)
        self.assertEqual(1, factory_called)


if __name__ == '__main__':
    unittest.main()
