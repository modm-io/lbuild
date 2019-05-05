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
import enum
import unittest

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

from lbuild.collector import *
from lbuild.repository import Repository
import lbuild.exception as le


class CollectorTest(unittest.TestCase):

    def setUp(self):
        repoinit = lbuild.repository.RepositoryInit(None, "path")
        repoinit.name = "repo"
        self.repo = lbuild.repository.Repository(repoinit)

        module1 = lbuild.module.ModuleInit(self.repo, "filename")
        module1.parent = self.repo.name
        module1.name = "module1"
        module1.available = True

        module2 = lbuild.module.ModuleInit(self.repo, "filename2")
        module2.parent = self.repo.name
        module2.name = "module2"
        module2.available = True

        self.module1, self.module2 = lbuild.module.build_modules([module1, module2])

        # Disable advanced formatting for a console and use the plain output
        lbuild.format.PLAIN = True

    def test_should_provide_factsheet(self):
        collector = Collector(StringCollector("test", "long description"))
        output = collector.description

        self.assertIn("test  [StringCollector]", output)
        self.assertNotIn("Value:", output)
        self.assertIn("Inputs: [String]", output)
        self.assertIn("long description", output)

    def test_should_access_values(self):
        collector = Collector(NumericCollector("test", "long description"))

        collector.add_values(1, self.module1)
        collector.add_values(2, self.module1)

        collector.add_values(2, self.module2)
        collector.add_values([3, 3], self.module2)

        unique_values = collector.values()
        unique_values1 = collector.values(filterfunc=lambda s: s.module == "repo:module1")
        unique_values2 = collector.values(filterfunc=lambda s: s.module == "repo:module2")

        all_values = collector.values(unique=False)
        all_values1 = collector.values(filterfunc=lambda s: s.module == "repo:module1", unique=False)
        all_values2 = collector.values(filterfunc=lambda s: s.module == "repo:module2", unique=False)

        self.assertEqual([1, 2, 3], unique_values)
        self.assertEqual([1, 2], unique_values1)
        self.assertEqual([2, 3], unique_values2)

        self.assertEqual([1, 2, 2, 3, 3], all_values)
        self.assertEqual([1, 2], all_values1)
        self.assertEqual([2, 3, 3], all_values2)


    def test_should_be_constructable_from_callable(self):
        collector = Collector(CallableCollector("test", "long description"))
        output = collector.description

        self.assertIn("test  [CallableCollector]", output)
        self.assertIn("Inputs: [Callable]", output)
        self.assertIn("long description", output)

        def function():
            pass
        collector.add_values(function, self.module1)
        self.assertEqual([function], collector.values())

        self.assertRaises(le.LbuildOptionInputException,
                          lambda: collector.add_values(1, self.module1))


if __name__ == '__main__':
    unittest.main()
