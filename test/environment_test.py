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
import shutil
import tempfile
import unittest
from unittest import mock

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.exception as le


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


    def _patch_environment(self, patch):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        repo = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(repo, "folder"))
        for name in ["file.c", "folder/a.c", "folder/b.c"]:
            with open(os.path.join(repo, name), "w") as file:
                file.write("one\ntwo\nthree\n")
        with open(os.path.join(repo, "template.c.in"), "w") as file:
            # Jinja2 removes a single trailing newline
            file.write("{{ value }}\ntwo\nthree\n\n")
        with open(os.path.join(repo, "fix.patch"), "w") as file:
            file.write(patch)
        env = self._environment(repo, os.path.join(tmp, "out"), tmp)
        env.outbasepath = "base"
        return env, repo

    @staticmethod
    def _diff(path, old="two", new="TWO", first="one"):
        return ("diff --git a/{0} b/{0}\n--- a/{0}\n+++ b/{0}\n"
                "@@ -1,3 +1,3 @@\n {3}\n-{1}\n+{2}\n three\n".format(path, old, new, first))

    def _read(self, env, path):
        with open(env.outpath(path)) as file:
            return file.read()

    def test_should_patch_copied_file(self):
        env, repo = self._patch_environment(self._diff("renamed.c"))
        env.copy("file.c", "renamed.c", patch="fix.patch")
        self.assertEqual("one\nTWO\nthree\n", self._read(env, "renamed.c"))
        # The source must not be modified
        with open(os.path.join(repo, "file.c")) as file:
            self.assertEqual("one\ntwo\nthree\n", file.read())

    def test_should_patch_copied_folder(self):
        env, _ = self._patch_environment(self._diff("dir/b.c"))
        env.copy("folder", "dir", patch="fix.patch")
        self.assertEqual("one\ntwo\nthree\n", self._read(env, "dir/a.c"))
        self.assertEqual("one\nTWO\nthree\n", self._read(env, "dir/b.c"))

    def test_should_skip_patch_of_ignored_files(self):
        patch = self._diff("dir/a.c") + self._diff("dir/b.c")
        env, repo = self._patch_environment(patch)
        env.copy("folder", "dir", ignore=lbuild.utils.ignore_files("b.c"), patch="fix.patch")
        self.assertEqual("one\nTWO\nthree\n", self._read(env, "dir/a.c"))
        self.assertFalse(os.path.exists(env.outpath("dir/b.c")))
        with open(os.path.join(repo, "folder/b.c")) as file:
            self.assertEqual("one\ntwo\nthree\n", file.read())

        failures = [
            # Ignored files must still be patchable
            self._diff("dir/a.c") + self._diff("dir/b.c", old="zwei"),
            # Files missing in the source folder
            patch + self._diff("dir/c.c"),
        ]
        for patch in failures:
            with self.subTest(patch=patch):
                env, _ = self._patch_environment(patch)
                with self.assertRaises(le.LbuildEnvironmentPatchException):
                    env.copy("folder", "dir", ignore=lbuild.utils.ignore_files("b.c"), patch="fix.patch")

    def test_should_patch_files_with_crlf_line_endings(self):
        for crlf_file, crlf_patch in [(True, False), (False, True), (True, True)]:
            with self.subTest(crlf_file=crlf_file, crlf_patch=crlf_patch):
                patch = self._diff("file.c")
                env, repo = self._patch_environment(patch.replace("\n", "\r\n") if crlf_patch else patch)
                if crlf_file:
                    with open(os.path.join(repo, "file.c"), "w", newline="\r\n") as file:
                        file.write("one\ntwo\nthree\n")
                env.copy("file.c", patch="fix.patch")
                with open(env.outpath("file.c"), "rb") as file:
                    content = b"one\nTWO\nthree\n"
                    self.assertEqual(content.replace(b"\n", b"\r\n") if crlf_file else content, file.read())

    def test_should_patch_templated_file(self):
        env, _ = self._patch_environment(self._diff("template.c", first="1"))
        env.template("template.c.in", substitutions={"value": 1}, patch="fix.patch")
        self.assertEqual("1\nTWO\nthree\n", self._read(env, "template.c"))

    def test_should_patch_symlinked_copy_without_modifying_source(self):
        env, repo = self._patch_environment(self._diff("file.c"))
        with mock.patch("lbuild.environment.SYMLINK_ON_COPY", True):
            env.copy("file.c", patch="fix.patch")
        self.assertEqual("one\nTWO\nthree\n", self._read(env, "file.c"))
        with open(os.path.join(repo, "file.c")) as file:
            self.assertEqual("one\ntwo\nthree\n", file.read())

    def test_should_raise_when_patch_does_not_apply(self):
        failures = [
            # Context does not match the file
            self._diff("file.c", old="zwei"),
            # File is not generated by this operation
            self._diff("file.c") + self._diff("other.c"),
            # File is outside the output path
            self._diff("../file.c"),
            # Context is at a different line
            self._diff("file.c").replace("-1,3 +1,3", "-2,3 +2,3"),
            # File is already patched
            self._diff("file.c", old="TWO", new="two"),
            # Files are not created or deleted
            "--- /dev/null\n+++ b/new.c\n@@ -0,0 +1 @@\n+new\n",
            # Not a patch at all
            "garbage\n",
        ]
        for patch in failures:
            with self.subTest(patch=patch):
                env, _ = self._patch_environment(patch)
                with self.assertRaises(le.LbuildEnvironmentPatchException):
                    env.copy("file.c", patch="fix.patch")

    def test_should_raise_when_patch_is_missing(self):
        env, _ = self._patch_environment("")
        with self.assertRaises(le.LbuildEnvironmentFileNotFoundException):
            env.copy("file.c", patch="missing.patch")


if __name__ == '__main__':
    unittest.main()
