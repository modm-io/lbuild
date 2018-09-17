#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os

import lbuild.environment
from lbuild.buildlog import BuildLog
from lbuild.parser import Parser
from lbuild.config import ConfigNode
from lbuild.utils import listify, listrify

class Builder:
    def __init__(self, cwd=None, config=None, options=None):
        if cwd is None:
            cwd = os.getcwd()
        os.chdir(cwd)
        self.cwd = cwd

        config = ConfigNode.from_file(config, fail_silent=True)
        file_config = ConfigNode.from_filesystem(cwd)
        if config:
            config.extend_last(file_config)
        else:
            config = file_config if file_config else ConfigNode()

        self.config = config
        self.config.add_commandline_options(listify(options))
        self.parser = Parser(self.config)

    def _load_repositories(self, repos=None):
        self.parser.load_repositories(listrify(repos))
        self.parser.merge_repository_options()

    def _load_modules(self):
        if not len(self.parser._undefined_repo_options()):
            self.parser.prepare_repositories()
            self.parser.merge_module_options()

    def _filter_modules(self, modules=None):
        self.parser.config.modules.extend(listify(modules))
        selected_modules = self.parser.find_modules(self.parser.config.modules)
        return self.parser.resolve_dependencies(selected_modules)


    def load(self, repos=None):
        self._load_repositories(repos)
        self._load_modules()

    def validate(self, modules=None):
        build_modules = self._filter_modules(modules)
        self.parser.validate_modules(build_modules)

    def build(self, outpath, modules=None, simulate=False):
        build_modules = self._filter_modules(modules)
        buildlog = BuildLog(outpath)
        lbuild.environment.simulate = simulate
        self.parser.build_modules(build_modules, buildlog)
        return buildlog