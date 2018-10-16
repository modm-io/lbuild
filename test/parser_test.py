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
import testfixtures

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild


class ParserTest(unittest.TestCase):

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "parser", filename)

    @staticmethod
    def prepare_modules(parser, selected=None, configoptions={}):
        if selected is None:
            selected_module_names = [":**"]
        else:
            selected_module_names = selected

        parser.config.options.update(configoptions)
        parser.merge_repository_options()
        modules = parser.prepare_repositories()
        parser.merge_module_options()

        selected_modules = parser.find_modules(selected_module_names)
        build_modules = parser.resolve_dependencies(selected_modules)

        return build_modules

    def setUp(self):
        self.parser = lbuild.parser.Parser()

    def test_should_parse_repository_1(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.assertEqual(1, len(self.parser.repositories))

    def test_should_find_files_in_repository_1(self):
        repo = self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.merge_repository_options()
        self.parser.prepare_repositories()

        self.assertEqual(6, len(repo.modules))
        # "repo1:other" is not available with the selected repository options
        self.assertIn("repo1:module1", repo.modules)
        self.assertIn("repo1:module2", repo.modules)
        self.assertIn("repo1:module2:submodule3", repo.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", repo.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", repo.modules)

    def test_should_find_files_in_repository_2(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        repo = self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.assertEqual(2, len(self.parser.repositories))
        self.parser.merge_repository_options()
        self.parser.prepare_repositories()

        self.assertEqual(4, len(repo.modules))
        self.assertIn("repo2:module3", repo.modules)
        self.assertIn("repo2:module4", repo.modules)
        self.assertIn("repo2:module4:submodule1", repo.modules)
        self.assertIn("repo2:module4:submodule2", repo.modules)

    def test_repository_should_contain_options(self):
        repo = self.parser.parse_repository(self._get_path("repository_options/repo.lb"))
        options = self.parser.repo_options

        self.assertIn("repository_options:target", options)
        self.assertIn("repository_options:foo", options)

        self.assertEqual(76, options["repository_options:foo"].value)

    def test_should_parse_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.merge_repository_options()
        self.parser.prepare_repositories()

        self.assertEqual(6, len(self.parser.modules))
        # "repo1:other" is not available with the selected repository options
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:module2:submodule3", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", self.parser.modules)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", self.parser.modules)

    def test_should_parse_modules_from_multiple_repositories(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.parser.merge_repository_options()
        self.parser.prepare_repositories()

        self.assertEqual(10, len(self.parser.modules))
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

    def test_should_merge_options(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.parser._config_flat = lbuild.config.ConfigNode.from_file(self._get_path("combined/test1.xml"))
        self.parser.merge_repository_options()
        options = self.parser.repo_options

        self.assertEqual("hosted", options["repo1:target"].value)
        self.assertEqual(43, options["repo1:foo"].value)
        self.assertEqual("tree", options["repo2:target"].value)
        self.assertEqual(True, options["repo2:include_tests"].value)

    def test_should_select_available_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.parser._config_flat = lbuild.config.ConfigNode.from_file(self._get_path("combined/test1.xml"))

        self.parser.merge_repository_options()
        modules = self.parser.prepare_repositories()

        self.assertIn("repo1:other", self.parser.modules)
        self.assertIn("repo1:module1", self.parser.modules)

    def test_raise_unknown_module(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser._config_flat = lbuild.config.ConfigNode.from_file(self._get_path("combined/test1.xml"))

        self.parser.merge_repository_options()
        modules = self.parser.prepare_repositories()
        self.parser.config.modules.append(":unknown")
        self.assertRaises(lbuild.exception.LbuildException,
                          lambda: self.parser.find_modules(self.parser.config.modules))

    def _get_build_modules(self):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))
        self.parser._config_flat = lbuild.config.ConfigNode.from_file(self._get_path("combined/test1.xml"))

        self.parser.merge_repository_options()
        modules = self.parser.prepare_repositories()
        selected_modules = self.parser.find_modules(self.parser.config.modules)
        build_modules = self.parser.resolve_dependencies(selected_modules)

        return build_modules, self.parser.config.options

    def test_should_resolve_module_dependencies(self):
        build_modules, _ = self._get_build_modules()

        self.assertEqual(7, len(build_modules))

        m = [x.fullname for x in build_modules]
        self.assertIn("repo1:other", m)
        self.assertIn("repo1:module1", m)
        self.assertIn("repo2:module4", m)
        self.assertIn("repo1:module2", m)
        self.assertIn("repo1:module2:submodule3", m)
        self.assertIn("repo1:module2:submodule3:subsubmodule1", m)
        self.assertIn("repo1:module2:submodule3:subsubmodule2", m)

    def test_should_merge_build_module_options(self):
        build_modules, config_options = self._get_build_modules()
        self.parser.merge_module_options()
        options = self.parser.module_options

        self.assertEqual(6, len(options))
        self.assertEqual(456, options["repo1:other:foo"].value)
        self.assertEqual(768, options["repo1:other:bar"].value)
        self.assertEqual(False, options["repo1:other:xyz"].value)
        self.assertEqual("Hello World!", options["repo1:other:abc"].value)
        self.assertEqual(15, options["repo1:module2:submodule3:subsubmodule1:price"].value)
        self.assertEqual(True, options["repo1:module2:submodule3:subsubmodule2:option1"].value)

    @testfixtures.tempdir()
    def test_should_build_modules(self, tempdir):
        build_modules, config_options = self._get_build_modules()
        module_options = self.parser.merge_module_options()

        outpath = tempdir.path
        log = lbuild.buildlog.BuildLog(outpath)
        self.parser.build_modules(build_modules, log)

        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/other.cpp")))
        self.assertTrue(os.path.isfile(os.path.join(outpath, "test/other.cpp")))

    @testfixtures.tempdir()
    def test_should_build_archive_modules(self, tempdir):
        self.parser.parse_repository(self._get_path("archive/repo.lb"))
        build_modules = self.prepare_modules(self.parser)

        outpath = tempdir.path
        log = lbuild.buildlog.BuildLog(outpath)
        self.parser.build_modules(build_modules, log)

        # for path, dirs, files in os.walk(outpath):
        #     for f in files:
        #         print(os.path.join(path, f))

        paths = [
            # complete extraction
            "zip/all/file.txt",
            "zip/all/file.hpp",
            "zip/all/folder/file.txt",
            "zip/all/folder/file.hpp",

            "zip/all/renamed/file.txt",
            "zip/all/renamed/file.hpp",
            "zip/all/renamed/folder/file.txt",
            "zip/all/renamed/folder/file.hpp",

            "zip/all/ignored/file.txt",
            "zip/all/ignored/file.hpp",
            "!zip/all/ignored/folder/file.txt",
            "!zip/all/ignored/folder/file.hpp",

            # partial folder extraction
            "zip/folders/folder/file.txt",
            "zip/folders/folder/file.hpp",
            "!zip/folders/file.txt",
            "!zip/folders/file.hpp",

            "zip/folders/renamed/file.txt",
            "zip/folders/renamed/file.hpp",

            "zip/folders/ignored/file.hpp",
            "!zip/folders/ignored/file.txt",

            # partial file extraction
            "zip/files/file.txt",
            "!zip/files/file.hpp",

            "zip/files/file2.txt",

            "!zip/files/file3.txt",

            # complete extraction
            "tar/all/file.txt",
            "tar/all/file.hpp",
            "tar/all/folder/file.txt",
            "tar/all/folder/file.hpp",

            "tar/all/renamed/file.txt",
            "tar/all/renamed/file.hpp",
            "tar/all/renamed/folder/file.txt",
            "tar/all/renamed/folder/file.hpp",

            "tar/all/ignored/file.txt",
            "tar/all/ignored/file.hpp",
            "!tar/all/ignored/folder/file.txt",
            "!tar/all/ignored/folder/file.hpp",

            # partial folder extraction
            "tar/folders/folder/file.txt",
            "tar/folders/folder/file.hpp",
            "!tar/folders/file.txt",
            "!tar/folders/file.hpp",

            "tar/folders/renamed/file.txt",
            "tar/folders/renamed/file.hpp",

            "tar/folders/ignored/file.hpp",
            "!tar/folders/ignored/file.txt",

            # partial file extraction
            "tar/files/file.txt",
            "!tar/files/file.hpp",

            "tar/files/file2.txt",

            "!tar/files/file3.txt",
        ]

        for path in paths:
            if path.startswith("!"):
                path = os.path.join(outpath, path[1:])
                self.assertFalse(os.path.exists(path))
            else:
                path = os.path.join(outpath, path)
                self.assertTrue(os.path.isfile(path))

    @testfixtures.tempdir()
    def test_should_build_jinja_2_modules(self, tempdir):
        self.parser.parse_repository(self._get_path("combined/repo1.lb"))
        self.parser.parse_repository(self._get_path("combined/repo2/repo2.lb"))

        selected_modules = ["repo2:module3"]
        config_options = {
            'repo1:target': 'hosted',
            ':other:xyz': 'No',
            'repo1::bar': '768',
            'repo1:other:foo': '456',
            '::abc': 'Hello World!',
        }
        build_modules = self.prepare_modules(self.parser, selected_modules, config_options)

        outpath = tempdir.path
        log = lbuild.buildlog.BuildLog(outpath)
        self.parser.build_modules(build_modules, log)

        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/module3.cpp")))

        testfixtures.compare(tempdir.read("src/module3.cpp"), b"Hello World!")

    @testfixtures.tempdir()
    def test_should_raise_when_overwriting_file(self, tempdir):
        self.parser.parse_repository(self._get_path("overwrite_file/repo.lb"))
        build_modules = self.prepare_modules(self.parser)

        outpath = tempdir.path
        log = lbuild.buildlog.BuildLog(outpath)
        self.assertRaises(lbuild.exception.LbuildBuildException,
                          lambda: self.parser.build_modules(build_modules, log))

    @testfixtures.tempdir()
    def test_should_raise_when_overwriting_file_in_tree(self, tempdir):
        self.parser.parse_repository(self._get_path("overwrite_file_in_tree/repo.lb"))
        build_modules = self.prepare_modules(self.parser)

        outpath = tempdir.path
        log = lbuild.buildlog.BuildLog(outpath)
        self.assertRaises(lbuild.exception.LbuildBuildException,
                          lambda: self.parser.build_modules(build_modules, log))

    @testfixtures.tempdir()
    def test_should_raise_when_no_module_is_found(self, tempdir):
        self.parser.parse_repository(self._get_path("empty_repository/repo.lb"))

        self.assertRaises(lbuild.exception.LbuildBuildException,
                          lambda: self.prepare_modules(self.parser))

    @testfixtures.tempdir()
    def test_should_parse_optional_functions_in_module(self, tempdir):
        self.parser.parse_repository(self._get_path("optional_functions/repo.lb"))
        self.prepare_modules(self.parser)

        module1 = self.parser.find_module(":module1")
        module2 = self.parser.find_module(":module2")

        self.assertIsNone(module1._functions.get("validate", None))
        self.assertIsNone(module1._functions.get("pre_build", None)) # deprecated
        self.assertIsNone(module1._functions.get("post_build", None))
        self.assertIsNotNone(module2._functions.get("validate", None))
        self.assertIsNotNone(module2._functions.get("pre_build", None)) # deprecated
        self.assertIsNotNone(module2._functions.get("post_build", None))

if __name__ == '__main__':
    unittest.main()
