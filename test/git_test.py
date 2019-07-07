#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import tarfile
import warnings
import unittest
import testfixtures

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild

class GitTest(unittest.TestCase):
    """
    Uses a local (compressed) Git repository to verify the functionality of
    the Git module.
    """

    def _get_path(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "resources", "git", filename)

    def prepare_git_repository(self, tempdir):
        """
        Extract the Git repository.
        """
        with tarfile.TarFile(self._get_path("repository.tar")) as archive:
            archive.extractall(tempdir.path)

    def prepare_config_file(self, tempdir, branch="", commit=""):
        config_filename = tempdir.getpath("config.xml")
        localpath = tempdir.getpath("source")
        url = tempdir.getpath("repository")
        branch = "<branch>{}</branch>".format(branch) if branch else ""
        commit = "<commit>{}</commit>".format(commit) if commit else ""

        with open(config_filename, "w") as config_file:
            with open(self._get_path("config.xml.in")) as template:
                config_input = template.read()
            config_file.write(config_input.format(localpath=localpath,
                                                  url=url,
                                                  branch=branch,
                                                  commit=commit))
        return config_filename

    @staticmethod
    def prepare_arguments(config_file, commands):
        """
        Prepare the command-line arguments.

        Adds the path to the generated config file.
        """
        argument_parser = lbuild.main.prepare_argument_parser()
        commandline_arguments = ["-c{}".format(config_file), ]
        commandline_arguments.extend(commands)
        args = argument_parser.parse_args(commandline_arguments)
        return args

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository(self, tempdir):
        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir)
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository_multiple_times(self, tempdir):
        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir)
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository_with_exisiting_repository(self, tempdir):
        self.prepare_git_repository(tempdir)

        # Add existing source directory with default checkout of 'master' branch
        config_file = self.prepare_config_file(tempdir)
        args = self.prepare_arguments(config_file, ["init", ])
        lbuild.main.run(args)

        # Checkout with 'develop' branch
        config_file = self.prepare_config_file(tempdir, branch="develop")
        args = self.prepare_arguments(config_file, ["init", ])

        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "module3.lb",
            "module4.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_update_repository_after_initialize(self, tempdir):
        # GitPython does not release a handle to /dev/null is some cases. This
        # is a known problem but has not been fixed yet. Suppress the
        # warning for this test to avoid cluttering up the output.
        warnings.simplefilter("ignore", ResourceWarning)

        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir)
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        args = self.prepare_arguments(config_file, ["update", ])

        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository_with_different_branch(self, tempdir):
        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir, branch="develop")
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "module3.lb",
            "module4.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository_with_head_commit(self, tempdir):
        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir,
                                               branch="ignored",
                                               commit="fbfc82c8f77c7bb8676925a0f1dce196a55f1140")
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "module3.lb",
            "module4.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")

    @testfixtures.tempdir(ignore=[".git/"])
    def test_should_initialize_repository_with_different_commit(self, tempdir):
        self.prepare_git_repository(tempdir)
        config_file = self.prepare_config_file(tempdir,
                                               branch="ignored",
                                               commit="1671afbce8453c1e6c0f4c94c6d9ede2c5f49991")
        args = self.prepare_arguments(config_file, ["init", ])

        # Run the command
        output = lbuild.main.run(args)
        self.assertEqual("", output)

        tempdir.compare([
            "repo.lb",
            "module1.lb",
            "module3.lb",
            "folder/",
            "folder/module2.lb",
            ], path="source")
