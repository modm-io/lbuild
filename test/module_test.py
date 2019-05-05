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

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
from lbuild.option import *
import lbuild.exception as le
import lbuild.module as lm

class ModuleTest(unittest.TestCase):

    def setUp(self):
        repoinit = lbuild.repository.RepositoryInit(None, ".")
        repoinit.name = "repo"
        self.repo = lbuild.repository.Repository(repoinit)

    def test_module_load_from_invalid_object(self):
        with self.assertRaises(le.LbuildNodeMissingFunctionException):
            class NoFunctions:
                pass
            lm.load_module_from_object(self.repo, NoFunctions(), __file__)

        with self.assertRaises(le.LbuildModuleNoNameException):
            class NoName:
                def init(self, module):
                    pass
                def prepare(self, module, option):
                    pass
                def build(self, env):
                    pass
            lm.load_module_from_object(self.repo, NoName(), __file__)

        with self.assertRaises(le.LbuildModuleNoReturnAvailableException):
            class NoPrepareReturn:
                def init(self, module):
                    module.name = "repo:module:submodule"
                def prepare(self, module, option):
                    pass
                def build(self, env):
                    pass
            lm.load_module_from_object(self.repo, NoPrepareReturn(), __file__)

        with self.assertRaises(le.LbuildNodeMissingFunctionException):
            class SubmoduleNoFunctions:
                def init(self, module):
                    module.name = "repo:module:submodule"
                def prepare(self, module, option):
                    class Submodule:
                        pass
                    module.add_submodule(Submodule())
                    return True
                def build(self, env):
                    pass
            lm.load_module_from_object(self.repo, SubmoduleNoFunctions(), __file__)

        with self.assertRaises(le.LbuildModuleDuplicateChildException):
            class ModuleDuplicateChild:
                def init(self, module):
                    module.name = "repo:module:submodule"
                def prepare(self, module, option):
                    module.add_option(BooleanOption("conflict", ""))
                    module.add_option(BooleanOption("conflict", ""))
                    return True
                def build(self, env):
                    pass
            moduleinit, = lm.load_module_from_object(self.repo, ModuleDuplicateChild(), __file__)
            lm.Module(moduleinit)

    def test_module_name_test(self):

        def _test_name(valid, name, parent=None):
            class ModuleName:
                def init(self, module):
                    module.name = name
                    if parent is not None:
                        module.parent = parent
                def prepare(self, module, option):
                    return True
                def build(self, env):
                    pass
            moduleinit, = lm.load_module_from_object(self.repo, ModuleName(), __file__)
            self.assertEqual(valid, moduleinit.fullname)

        _test_name("repo:name", "name")
        _test_name("repo:repo:name", "name", "repo")
        _test_name("repo:repo:name", "name", ":repo")
        _test_name("repo:other:name", "name", "other")
        _test_name("repo:other:name", "name", ":other")

        _test_name("repo:name", ":name")
        _test_name("repo:name", "repo:name")
        _test_name("repo:repo:name", ":name", "repo")
        _test_name("repo:repo:name", ":name", ":repo")
        _test_name("repo:repo:name", ":name", "repo:repo")
        _test_name("repo:other:name", ":name", "other")
        _test_name("repo:other:name", ":name", ":other")
        _test_name("repo:other:name", ":name", "repo:other")

        _test_name("repo:parent:name", "parent:name")
        _test_name("repo:repo:parent:name", "parent:name", "repo")
        _test_name("repo:repo:parent:name", "parent:name", ":repo")
        _test_name("repo:repo:parent:name", "parent:name", "repo:repo")
        _test_name("repo:other:parent:name", "parent:name", "other")
        _test_name("repo:other:parent:name", "parent:name", ":other")
        _test_name("repo:other:parent:name", "parent:name", "repo:other")

        _test_name("repo:parent:name", ":parent:name")
        _test_name("repo:parent:name", "repo:parent:name")
        _test_name("repo:repo:parent:name", ":parent:name", "repo")
        _test_name("repo:repo:parent:name", ":parent:name", ":repo")
        _test_name("repo:repo:parent:name", ":parent:name", "repo:repo")
        _test_name("repo:other:parent:name", ":parent:name", "other")
        _test_name("repo:other:parent:name", ":parent:name", ":other")
        _test_name("repo:other:parent:name", ":parent:name", "repo:other")

        _test_name("repo:parent:name", "name", "repo:parent")
        _test_name("repo:repo:parent:name", "name", ":repo:parent")
        _test_name("repo:repo:parent:name", "name", "repo:repo:parent")
        _test_name("repo:other:parent:name", "name", "other:parent")
        _test_name("repo:other:parent:name", "name", ":other:parent")
        _test_name("repo:other:parent:name", "name", "repo:other:parent")

        _test_name("repo:parent:name", ":name", "repo:parent")
        _test_name("repo:repo:parent:name", ":name", ":repo:parent")
        _test_name("repo:repo:parent:name", ":name", "repo:repo:parent")
        _test_name("repo:other:parent:name", ":name", "other:parent")
        _test_name("repo:other:parent:name", ":name", ":other:parent")
        _test_name("repo:other:parent:name", ":name", "repo:other:parent")

        _test_name("repo:parent:parent:name", "parent:name", "repo:parent")
        _test_name("repo:repo:parent:parent:name", "parent:name", ":repo:parent")
        _test_name("repo:repo:parent:parent:name", "parent:name", "repo:repo:parent")
        _test_name("repo:other:parent:parent:name", "parent:name", "other:parent")
        _test_name("repo:other:parent:parent:name", "parent:name", ":other:parent")
        _test_name("repo:other:parent:parent:name", "parent:name", "repo:other:parent")

        _test_name("repo:parent:parent:name", ":parent:name", "repo:parent")
        _test_name("repo:repo:parent:parent:name", ":parent:name", ":repo:parent")
        _test_name("repo:repo:parent:parent:name", ":parent:name", "repo:repo:parent")
        _test_name("repo:other:parent:parent:name", ":parent:name", "other:parent")
        _test_name("repo:other:parent:parent:name", ":parent:name", ":other:parent")
        _test_name("repo:other:parent:parent:name", ":parent:name", "repo:other:parent")





if __name__ == '__main__':
    unittest.main()
