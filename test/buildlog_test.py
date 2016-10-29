#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
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
        self.repo = lbuild.repository.Repository(".")
        self.repo.name = "repo"

        self.module1 = lbuild.module.Module(self.repo, "module.lb", ".")
        self.module1.name = "module1"
        self.module1.register_module()

        self.module2 = lbuild.module.Module(self.repo, "module.lb", ".")
        self.module2.name = "module2"
        self.module2.register_module()

    def test_should_collect_operations(self):
        log = lbuild.buildlog.BuildLog()

        log.log(self.module1, "in1", "out1")
        log.log(self.module1, "in2", "out2")

        self.assertEqual(2, len(log.operations))

    def test_should_raise_on_overwriting_a_file(self):
        log = lbuild.buildlog.BuildLog()

        log.log(self.module1, "in", "out")
        self.assertRaises(lbuild.exception.BlobBuildException,
                          lambda: log.log(self.module1, "in", "out"))

    def test_should_generate_xml(self):
        log = lbuild.buildlog.BuildLog()

        log.log(self.module1, "in1", "out1")
        log.log(self.module2, "in2", "out2")

        self.assertEqual(b"""<?xml version='1.0' encoding='UTF-8'?>
<buildlog>
  <operation>
    <module>repo:module1</module>
    <source>in1</source>
    <destination>out1</destination>
  </operation>
  <operation>
    <module>repo:module2</module>
    <source>in2</source>
    <destination>out2</destination>
  </operation>
</buildlog>
""", log.to_xml())

if __name__ == '__main__':
    unittest.main()
