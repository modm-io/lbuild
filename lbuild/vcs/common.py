#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import enum
import logging

import lbuild.config
from ..exception import LbuildException

LOGGER = logging.getLogger('lbuild.vcs')


class Action(enum.Enum):
    init = 0
    update = 1


def _parse_vcs(config: lbuild.config.ConfigNode,
               action):
    LOGGER.debug("Initialize VCS repositories")

    config = config.flatten()
    for vcs in config.vcs:
        for tag, repoconfig in vcs.items():
            if tag == "git":
                LOGGER.debug("Found Git repository")

                from . import git
                repo = git.Repository(config.cachefolder, repoconfig)
            else:
                raise LbuildException("Unsupported VCS type '{}'".format(tag))

            if action == Action.init:
                repo.initialize()
            elif action == Action.update:
                repo.update()


def initialize(configfile):
    _parse_vcs(configfile, Action.init)


def update(configfile):
    _parse_vcs(configfile, Action.update)
