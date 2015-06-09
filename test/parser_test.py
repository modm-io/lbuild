#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
#import logging
import unittest

import blob

class ParserTest(unittest.TestCase):
	
	def _getPath(self, filename):
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
	
	def setUp(self):
		#logging.basicConfig(level=logging.DEBUG)
		self.parser = blob.parser.Parser()
	
	def test_shouldParseRepository1(self):
		self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		self.assertEqual(len(self.parser.repositories), 1)
	
	def test_shouldFindFilesInRepository1(self):
		repo = self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		
		self.assertEqual(len(repo.modules), 3)
		self.assertIn(self._getPath("resources/repo1/other.lb"), repo.modules)
		self.assertIn(self._getPath("resources/repo1/module1/module.lb"), repo.modules)
		self.assertIn(self._getPath("resources/repo1/module2/module.lb"), repo.modules)

	def test_shouldFindFilesInRepository2(self):
		repo = self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
		self.assertEqual(len(self.parser.repositories), 1)
		
		self.assertEqual(len(repo.modules), 4)
		self.assertIn(self._getPath("resources/repo2/module3/module.lb"), repo.modules)
		self.assertIn(self._getPath("resources/repo2/module4/module.lb"), repo.modules)
		self.assertIn(self._getPath("resources/repo2/module4/submodule1/module.lb"), repo.modules)
		self.assertIn(self._getPath("resources/repo2/module4/submodule2/module.lb"), repo.modules)

	def testRepository2HasOptions(self):
		repo = self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
		
		self.assertIn("target", repo.options)
		self.assertIn("include_tests", repo.options)
		
		self.assertEqual(repo.options["include_tests"].value, True)

	def test_shouldParseModules(self):
		self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		self.parser.parse_modules()
		
		self.assertEqual(len(self.parser.modules), 3)
		self.assertIn("repo1:module1", self.parser.modules)
		self.assertIn("repo1:module2", self.parser.modules)
		self.assertIn("repo1:other", self.parser.modules)

	def test_shouldParseModulesFromMultipleRepositories(self):
		self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
		self.parser.parse_modules()
		
		self.assertEqual(len(self.parser.modules), 7)
		self.assertIn("repo1:module1", self.parser.modules)
		self.assertIn("repo1:module2", self.parser.modules)
		self.assertIn("repo1:other", self.parser.modules)
		self.assertIn("repo2:module3", self.parser.modules)
		self.assertIn("repo2:module4", self.parser.modules)
		self.assertIn("repo2:module4.submodule1", self.parser.modules)
		self.assertIn("repo2:module4.submodule2", self.parser.modules)

if __name__ == '__main__':
	unittest.main()
