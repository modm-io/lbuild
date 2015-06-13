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
import unittest
import testfixtures
import shutil

import lbuild

class ParserTest(unittest.TestCase):
    
    def _getPath(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
    
    def setUp(self):
        self.parser = lbuild.parser.Parser()
    
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
        
        self.assertEqual("true", repo.options["include_tests"].value)

    def test_shouldParseModules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        
        self.assertEqual(len(self.parser.modules), 3)
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:other", self.parser.modules)

    def test_shouldParseModulesFromMultipleRepositories(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        
        self.assertEqual(len(self.parser.modules), 7)
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:other", self.parser.modules)
        self.assertIn("repo2:module3", self.parser.modules)
        self.assertIn("repo2:module4", self.parser.modules)
        self.assertIn("repo2:module4.submodule1", self.parser.modules)
        self.assertIn("repo2:module4.submodule2", self.parser.modules)
    
    def test_shouldParseConfigurationFile(self):
        modules, options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        self.assertEqual(2, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        
        self.assertEqual(3, len(options))
        self.assertEqual('hosted', options[':target'])
        self.assertEqual('456', options['repo1:other:foo'])
        self.assertEqual('768', options['repo1::bar'])

    def test_shouldMergeOptions(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        _, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        options = self.parser.merge_repository_options(config_options)
        self.assertEqual("hosted", options["repo1:target"].value)
        self.assertEqual("hosted", options["repo2:target"].value)
        self.assertEqual("true", options["repo2:include_tests"].value)
    
    def test_shouldSelectAvailableModules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        _, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_modules(options)
        
        self.assertIn("repo1:other", modules)
        self.assertIn("repo1:module1", modules)
    
    def _get_build_modules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        selected_modules, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        repo_options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_modules(repo_options)
        build_modules = self.parser.resolve_dependencies(modules, selected_modules)
        
        return build_modules, config_options, repo_options
      
    def test_shouldResolveModuleDependencies(self):
        build_modules, _, _ = self._get_build_modules()
        
        self.assertEqual(3, len(build_modules))
        
        m = [x.full_name for x in build_modules]
        self.assertIn("repo1:other", m)
        self.assertIn("repo1:module1", m)
        self.assertIn("repo2:module3", m)

    def test_shouldMergeBuildModuleOptions(self):
        build_modules, config_options, _ = self._get_build_modules()
        options = self.parser.merge_module_options(build_modules, config_options)
        
        self.assertEqual(2, len(options))
        self.assertEqual(options["repo1:other:foo"].value, "456")
        self.assertEqual(options["repo1:other:bar"].value, "768")

    def test_shouldBuildModules(self):
        build_modules, config_options, repo_options = self._get_build_modules()
        module_options = self.parser.merge_module_options(build_modules, config_options)
        
        outpath = "build"
        self.parser.build_modules(outpath, build_modules, repo_options, module_options)
        
        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/other.cpp")))
        self.assertTrue(os.path.isfile(os.path.join(outpath, "test/other.cpp")))
        
        shutil.rmtree(outpath)

if __name__ == '__main__':
    unittest.main()
