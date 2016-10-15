#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import enum
import logging

import lbuild.config
from ..exception import BlobException

LOGGER = logging.getLogger('lbuild.vcs')


class Action(enum.Enum):
    init = 0
    update = 1


def _parse_vcs(configfile, action):
    LOGGER.debug("Initialize VCS repositories")

    projectpath = os.path.dirname(configfile)
    cachefolder = os.path.join(projectpath, "lbuild_cache")

    xmltree = lbuild.config.load_and_verify(configfile)
    for vcs_node in xmltree.iterfind("repositories/repository/vcs"):
        for vcs in vcs_node.iterchildren():
            config = lbuild.config.to_dict(vcs)[vcs.tag]

            if vcs.tag == "git":
                LOGGER.debug("Found Git repository")

                from . import git
                repo = git.Repository(cachefolder, config)
            else:
                raise BlobException("Unsupported VCS type '{}'".format(vcs.tag))

            if action == Action.init:
                repo.initialize()
            elif action == Action.update:
                repo.update()

def initialize(configfile):
    _parse_vcs(configfile, Action.init)

def update(configfile):
    _parse_vcs(configfile, Action.update)
