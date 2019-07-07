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
import logging

import git

LOGGER = logging.getLogger('lbuild.vcs.git')


class Repository:

    def __init__(self, cachefolder, config):
        self.cachefolder = cachefolder

        self.name = config["name"]
        self.url = config["url"]
        self.branch = config.get("branch")
        self.commit = config.get("commit")

        self.localpath = os.path.join(cachefolder, self.name)
        self._repo = None

    def get_repository(self):
        if self._repo is None:
            if os.path.exists(self.localpath):
                LOGGER.info("Found existing repository in '%s'", os.path.relpath(self.localpath))
                self._repo = git.Repo(self.localpath)
            else:
                LOGGER.info("Cloning repository '%s' into '%s'", self.name, os.path.relpath(self.localpath))
                self._repo = git.Repo.clone_from(self.url, self.localpath)
        return self._repo

    def initialize(self):
        repo = self.get_repository()
        if self.commit is not None:
            self.switch_to_commit(repo, self.commit)
        elif self.branch is not None:
            self.switch_to_branch(repo, self.branch)
        LOGGER.info("Updating submodules recursively")
        repo.git.submodule('update', '--init', '--recursive')

    def update(self):
        repo = self.get_repository()
        LOGGER.info("Updating repository '%s' from origin", self.name)
        origin = repo.remotes.origin
        origin.pull()
        repo.git.submodule('sync')
        repo.git.submodule('update', '--recursive')

    @staticmethod
    def switch_to_commit(repo, commit):
        if not repo.head.commit.hexsha.startswith(commit):
            LOGGER.info("Switching to commit '%s'", commit)
            past_branch = repo.create_head("past_branch", commit)
            repo.head.reference = past_branch
            repo.head.reset(index=True, working_tree=True)
            repo.heads.past_branch.checkout()

    @staticmethod
    def switch_to_branch(repo, branch):
        active_branch = repo.active_branch
        if str(active_branch) != branch:
            LOGGER.info("Switching from branch '%s' to '%s'", active_branch, branch)
            git_cmd = repo.git
            git_cmd.checkout(branch)
