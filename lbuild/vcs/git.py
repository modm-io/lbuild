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

import pygit2

LOGGER = logging.getLogger('lbuild.vcs.git')


class _Callbacks(pygit2.RemoteCallbacks):
    """Authenticates SSH remotes via the SSH agent, like the git binary does."""

    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types & pygit2.enums.CredentialType.SSH_KEY:
            return pygit2.KeypairFromAgent(username_from_url or "git")
        return None


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
                self._repo = pygit2.Repository(self.localpath)
            else:
                LOGGER.info("Cloning repository '%s' into '%s'", self.name, os.path.relpath(self.localpath))
                self._repo = pygit2.clone_repository(self.url, self.localpath, callbacks=_Callbacks())
        return self._repo

    def initialize(self):
        repo = self.get_repository()
        if self.commit is not None:
            self.switch_to_commit(repo, self.commit)
        elif self.branch is not None:
            self.switch_to_branch(repo, self.branch)
        LOGGER.info("Updating submodules recursively")
        self.update_submodules(repo)

    def update(self):
        repo = self.get_repository()
        LOGGER.info("Updating repository '%s' from origin", self.name)
        repo.remotes["origin"].fetch(callbacks=_Callbacks())
        if not repo.head_is_detached:
            # Fast-forward only, like `git pull --ff-only`
            upstream = repo.branches.local[repo.head.shorthand].upstream
            if upstream is not None and upstream.target != repo.head.target:
                analysis, _ = repo.merge_analysis(upstream.target)
                if not analysis & pygit2.enums.MergeAnalysis.FASTFORWARD:
                    raise pygit2.GitError("Cannot fast-forward '{}' to '{}'!"
                                          .format(repo.head.shorthand, upstream.shorthand))
                repo.checkout_tree(repo[upstream.target])
                repo.head.set_target(upstream.target)
        self.update_submodules(repo, sync=True)

    @staticmethod
    def update_submodules(repo, sync=False):
        for submodule in repo.submodules:
            if sync:
                # Copy the URL from .gitmodules to .git/config, like `git submodule sync`
                submodule.init(overwrite=True)
            repo.submodules.update([submodule.path], init=True, callbacks=_Callbacks())
            subrepo = submodule.open()
            if sync:
                subrepo.remotes.set_url("origin", submodule.url)
            Repository.update_submodules(subrepo, sync)

    @staticmethod
    def switch_to_commit(repo, commit):
        if not str(repo.head.target).startswith(commit):
            LOGGER.info("Switching to commit '%s'", commit)
            target = repo.revparse_single(commit).peel(pygit2.Commit)
            past_branch = repo.branches.local.create("past_branch", target, force=True)
            repo.checkout(past_branch, strategy=pygit2.enums.CheckoutStrategy.FORCE)

    @staticmethod
    def switch_to_branch(repo, branch):
        active_branch = repo.head.shorthand
        if active_branch != branch:
            LOGGER.info("Switching from branch '%s' to '%s'", active_branch, branch)
            local = repo.branches.local.get(branch)
            if local is None:
                # Create a tracking branch, like `git checkout <branch>`
                remote = repo.branches.remote["origin/" + branch]
                local = repo.branches.local.create(branch, remote.peel(pygit2.Commit))
                local.upstream = remote
            repo.checkout(local)
