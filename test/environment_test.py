#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import ntpath
import unittest
from unittest import mock

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild


class EnvironmentTest(unittest.TestCase):

    def _environment(self, filepath, outpath, cwd):
        repoinit = lbuild.repository.RepositoryInit(None, filepath)
        repoinit.name = "repo"
        repo = lbuild.repository.Repository(repoinit)

        module = lbuild.module.ModuleInit(repo, os.path.join(filepath, "module.lb"))
        module.parent = repo.name
        module.name = "module"
        module.available = True
        module, = lbuild.module.build_modules([module])

        buildlog = lbuild.buildlog.BuildLog(outpath, cwd=cwd)
        return lbuild.environment.Environment(module, buildlog)

    def test_should_return_relative_paths(self):
        env = self._environment("/repo/m", "/project/out", "/project")

        self.assertEqual("out/modm/link", env.relcwdoutpath("modm/link"))
        self.assertEqual("modm/src", env.reloutpath("modm/src"))
        self.assertEqual("../ext/nanopb", env.reloutpath("ext/nanopb", "modm"))

        env.log_file("/repo/m/in", "/project/out/modm/src/out", 0)
        self.assertEqual(["modm/src/out"], env.generated_local_files())

    def test_should_return_relative_paths_with_forward_slashes(self):
        # Use the Windows path functions on every host
        names = ["join", "relpath", "dirname", "normpath", "basename", "isabs", "abspath"]
        with mock.patch.multiple("lbuild.buildlog", **{n: getattr(ntpath, n) for n in names}), \
             mock.patch("os.path", ntpath), mock.patch("os.sep", "\\"):
            env = self._environment("C:\\repo\\m", "C:\\project\\out", "C:\\project")

            self.assertEqual("out/modm/link", env.relcwdoutpath("modm\\link"))
            self.assertEqual("../build", env.relcwdoutpath("..\\..\\build"))
            self.assertEqual("modm/src", env.reloutpath("modm/src"))
            self.assertEqual("../ext/nanopb", env.reloutpath("ext\\nanopb", "modm"))
            self.assertEqual("../../build", env.reloutpath("..\\..\\build"))

            env.log_file("C:\\repo\\m\\in", "C:\\project\\out\\modm\\src\\out", 0)
            self.assertEqual(["modm/src/out"], env.generated_local_files())

            # Absolute paths remain native for file system access
            self.assertEqual("C:\\project\\out\\modm\\src", env.outpath("modm", "src"))
            self.assertEqual("C:\\project\\tools", env.cwdpath("tools"))
            self.assertEqual("C:\\repo\\m\\file", env.modulepath("file"))


if __name__ == '__main__':
    unittest.main()
