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
import unittest
import blob

class ParserTest(unittest.TestCase):
	
	def _getPath(self, filename):
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
	
	def setUp(self):
		self.parser = blob.parser.Parser()
	
	def test_shouldParseRepository1(self):
		self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		self.assertEqual(len(self.parser.repositories), 1)
	
	def test_shouldFindFilesInRepository1(self):
		self.parser.parse_repository(self._getPath("resources/repo1.lb"))
		repo = self.parser.repositories[0]
		
		self.assertEqual(len(repo.module_files), 3)
		self.assertTrue(self._getPath("resources/repo1/other.lb") in repo.module_files)
		self.assertTrue(self._getPath("resources/repo1/module1/module.lb") in repo.module_files)
		self.assertTrue(self._getPath("resources/repo1/module2/module.lb") in repo.module_files)

	def test_shouldFindFilesInRepository2(self):
		self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
		self.assertEqual(len(self.parser.repositories), 1)
		
		repo = self.parser.repositories[0]
		self.assertEqual(len(repo.module_files), 4)
		self.assertTrue(self._getPath("resources/repo2/module3/module.lb") in repo.module_files)
		self.assertTrue(self._getPath("resources/repo2/module4/module.lb") in repo.module_files)
		self.assertTrue(self._getPath("resources/repo2/module4/submodule1/module.lb") in repo.module_files)
		self.assertTrue(self._getPath("resources/repo2/module4/submodule2/module.lb") in repo.module_files)

if __name__ == '__main__':
	unittest.main()
