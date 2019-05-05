#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
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

import lbuild


class BuildLogTest(unittest.TestCase):

    def setUp(self):
        repoinit = lbuild.repository.RepositoryInit(None, ".")
        repoinit.name = "repo"
        self.repo = lbuild.repository.Repository(repoinit)

        module1 = lbuild.module.ModuleInit(self.repo, "/m1/module.lb")
        module1.parent = self.repo.name
        module1.name = "module1"
        module1.available = True

        module1a = lbuild.module.ModuleInit(self.repo, "/m1/a/module.lb")
        module1a.name = "module1a"
        module1a.parent = "repo:module1"
        module1a.available = True

        module2 = lbuild.module.ModuleInit(self.repo, "/m2/module.lb")
        module2.parent = self.repo.name
        module2.name = "module2"
        module2.available = True

        self.module1, self.module1a, self.module2 = \
            lbuild.module.build_modules([module1, module1a, module2])

        self.log = lbuild.buildlog.BuildLog("/")

    def test_should_collect_operations(self):
        o1 = self.log.log(self.module1, "in1", "out1")
        o2 = self.log.log(self.module1, "in2", "out2")

        self.assertEqual(2, len(self.log.operations))
        self.assertIn(o1, self.log.operations)
        self.assertIn(o2, self.log.operations)

    def test_should_raise_on_overwriting_a_file(self):
        self.log.log(self.module1, "in", "out")
        self.assertRaises(lbuild.exception.LbuildBuildlogOverwritingFileException,
                          lambda: self.log.log(self.module1, "in", "out"))

    def test_should_generate_xml(self):
        self.log.log(self.module1, "in1", "out1")
        self.log.log(self.module2, "in2", "out2")

        self.assertEqual(b"""<?xml version='1.0' encoding='UTF-8'?>
<buildlog>
  <outpath>.</outpath>
  <operation>
    <module>repo:module1</module>
    <source>m1/in1</source>
    <destination>out1</destination>
  </operation>
  <operation>
    <module>repo:module2</module>
    <source>m2/in2</source>
    <destination>out2</destination>
  </operation>
</buildlog>
""", self.log.to_xml(path="/"))

    def test_should_provide_operations_per_module(self):
        o1a = self.log.log(self.module1a, "in1a", "/out1a")
        o1 = self.log.log(self.module1, "in1", "/out1")
        o2 = self.log.log(self.module2, "in2", "/out2")

        operations = self.log.operations_per_module("repo:module1")
        self.assertIn(o1, operations)
        self.assertIn(o1a, operations)
        self.assertNotIn(o2, operations)

        self.assertEqual({"repo:module1", "repo:module1:module1a", "repo:module2"},
                         set(self.log.modules))
        self.assertEqual({"repo"}, set(self.log.repositories))

    def test_should_create_local_path(self):
        o1 = self.log.log(self.module1, "/m1/in1", "/test/out1")

        self.assertEqual("/m1/in1", o1.filename_in)
        self.assertEqual("in1", o1.local_filename_in())
        self.assertEqual("out1", o1.local_filename_out("test"))


if __name__ == '__main__':
    unittest.main()
