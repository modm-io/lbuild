#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import unittest
import testfixtures

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild


class ParserTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "parser", filename)

    @staticmethod
    def prepare_modules(parser, selected=None, config=None):
        if selected is None:
            selected = [":**"]
        if config is None:
            config = {}
        repo_options = parser.merge_repository_options(config)
        modules = parser.prepare_repositories(repo_options)
        build_modules = parser.resolve_dependencies(modules, selected)
        module_options = parser.merge_module_options(build_modules, config)
        return build_modules, repo_options, module_options

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def test_should_parse_repository_1(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.assertEqual(1, len(self.parser.repositories))

    def test_should_find_files_in_repository_1(self):
        repo = self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        repo_options = self.parser.merge_repository_options({})
        self.parser.prepare_repositories(repo_options)

        self.assertEqual(5, len(repo.modules))
        # "repo1:other" is not available with the selected repository options
        self.assertIn("repo1:module1", repo.modules)
        self.assertIn("repo1:module2", repo.modules)
        self.assertIn("repo1:module2:submodule3", repo.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", repo.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", repo.modules)

    def test_should_find_files_in_repository_2(self):
        repo = self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.assertEqual(1, len(self.parser.repositories))
        repo_options = self.parser.merge_repository_options({})
        self.parser.prepare_repositories(repo_options)

        self.assertEqual(4, len(repo.modules))
        self.assertIn("repo2:module3", repo.modules)
        self.assertIn("repo2:module4", repo.modules)
        self.assertIn("repo2:module4:submodule1", repo.modules)
        self.assertIn("repo2:module4:submodule2", repo.modules)

    def test_repository_should_contain_options(self):
        repo = self.parser.parse_repository(self._get_path("repository_options/repo.lb"))

        self.assertIn("target", repo.options)
        self.assertIn("foo", repo.options)

        self.assertEqual(76, repo.options["foo"].value)

    def test_should_parse_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        repo_options = self.parser.merge_repository_options({})
        self.parser.prepare_repositories(repo_options)

        self.assertEqual(5, len(self.parser.modules))
        # "repo1:other" is not available with the selected repository options
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:module2:submodule3", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", self.parser.modules)

    def test_should_parse_modules_from_multiple_repositories(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        repo_options = self.parser.merge_repository_options({})
        self.parser.prepare_repositories(repo_options)

        self.assertEqual(9, len(self.parser.modules))
        # "repo1:other" is not available with the selected repository options
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:module2:submodule3", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", self.parser.modules)
        self.assertIn("repo2:module3", self.parser.modules)
        self.assertIn("repo2:module4", self.parser.modules)
        self.assertIn("repo2:module4:submodule1", self.parser.modules)
        self.assertIn("repo2:module4:submodule2", self.parser.modules)

    def test_should_parse_configuration_file(self):
        modules, options = self.parser.parse_configuration(self._get_path("configfile/project.xml"))

        self.assertEqual(4, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        self.assertIn("::submodule3:subsubmodule1", modules)
        self.assertIn("::submodule3", modules)

        self.assertEqual(7, len(options))
        self.assertEqual('hosted', options[':target'])
        self.assertEqual('43', options['repo1:foo'])

        self.assertEqual('456', options['repo1:other:foo'])
        self.assertEqual('768', options['repo1::bar'])
        self.assertEqual('No', options[':other:xyz'])
        self.assertEqual('Hello World!', options['::abc'])
        self.assertEqual('15', options['::submodule3::price'])

    def test_should_merge_options(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        _, config_options = self.parser.parse_configuration(self._get_path("combined/test1.xml"))

        options = self.parser.merge_repository_options(config_options)
        self.assertEqual("hosted", options["repo1:target"].value)
        self.assertEqual(43, options["repo1:foo"].value)
        self.assertEqual("hosted", options["repo2:target"].value)
        self.assertEqual(True, options["repo2:include_tests"].value)

    def test_should_select_available_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        _, config_options = self.parser.parse_configuration(self._get_path("combined/test1.xml"))

        options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_repositories(options)

        self.assertIn("repo1:other", modules)
        self.assertIn("repo1:module1", modules)

    def _get_build_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        selected_modules, config_options = \
            self.parser.parse_configuration(self._get_path("combined/test1.xml"))

        repo_options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_repositories(repo_options)
        build_modules = self.parser.resolve_dependencies(modules, selected_modules)

        return build_modules, config_options, repo_options

    def test_should_resolve_module_dependencies(self):
        build_modules, _, _ = self._get_build_modules()

        self.assertEqual(6, len(build_modules))

        m = [x.fullname for x in build_modules]
        self.assertIn("repo1:other", m)
        self.assertIn("repo1:module1", m)
        self.assertIn("repo2:module4", m)
        self.assertIn("repo1:module2:submodule3", m)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", m)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", m)

    def test_should_merge_build_module_options(self):
        build_modules, config_options, _ = self._get_build_modules()
        options = self.parser.merge_module_options(build_modules, config_options)

        self.assertEqual(6, len(options))
        self.assertEqual(456, options["repo1:other:foo"].value)
        self.assertEqual(768, options["repo1:other:bar"].value)
        self.assertEqual(False, options["repo1:other:xyz"].value)
        self.assertEqual("Hello World!", options["repo1:other:abc"].value)
        self.assertEqual(15, options["repo1:module2:submodule3:subsubmodule1:price"].value)
        self.assertEqual(True, options["repo1:module2:submodule3:subsubmodule2:option1"].value)

    @testfixtures.tempdir()
    def test_should_build_modules(self, tempdir):
        build_modules, config_options, repo_options = self._get_build_modules()
        module_options = self.parser.merge_module_options(build_modules, config_options)

        log = lbuild.buildlog.BuildLog()

        outpath = tempdir.path
        self.parser.build_modules(outpath, build_modules, repo_options, module_options, log)

        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/other.cpp")))
        self.assertTrue(os.path.isfile(os.path.join(outpath, "test/other.cpp")))

    @testfixtures.tempdir()
    def test_should_build_jinja_2_modules(self, tempdir):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))

        selected_modules = ["repo2:module3"]
        config_options = {
            ':target': 'hosted',
            ':other:xyz': 'No',
            'repo1::bar': '768',
            'repo1:other:foo': '456',
            '::abc': 'Hello World!',
        }
        build_modules, repo_options, module_options = \
            self.prepare_modules(self.parser, selected_modules, config_options)

        log = lbuild.buildlog.BuildLog()

        outpath = tempdir.path
        self.parser.build_modules(outpath, build_modules, repo_options, module_options, log)

        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/module3.cpp")))

        testfixtures.compare(tempdir.read("src/module3.cpp"), b"Hello World!")

    @testfixtures.tempdir()
    def test_should_raise_when_overwriting_file(self, tempdir):
        self.parser.parse_repository(self._get_path("overwrite_file/repo.lb"))
        build_modules, repo_options, module_options = self.prepare_modules(self.parser)

        log = lbuild.buildlog.BuildLog()

        outpath = tempdir.path
        self.assertRaises(lbuild.exception.BlobBuildException,
                          lambda: self.parser.build_modules(outpath, build_modules, repo_options, module_options, log))

    @testfixtures.tempdir()
    def test_should_raise_when_overwriting_file_in_tree(self, tempdir):
        self.parser.parse_repository(self._get_path("overwrite_file_in_tree/repo.lb"))
        build_modules, repo_options, module_options = self.prepare_modules(self.parser)

        log = lbuild.buildlog.BuildLog()

        outpath = tempdir.path
        self.assertRaises(lbuild.exception.BlobBuildException,
                          lambda: self.parser.build_modules(outpath, build_modules, repo_options, module_options, log))

if __name__ == '__main__':
    unittest.main()
