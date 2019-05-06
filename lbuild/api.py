#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018, Niklas Hauser
# Copyright (c) 2018, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

"""
API for scripts extending/querying lbuild directly.
"""

import os

import lbuild.environment
from lbuild.buildlog import BuildLog
from lbuild.parser import Parser
from lbuild.config import ConfigNode
from lbuild.utils import listify, listrify


class Builder:

    def __init__(self, cwd=None, config=None, options=None):
        """
        Build instance to invoke lbuild methods.

        Args:
            cwd -- Current working directly. If specified lbuild will
                search for a configuration file in this folder.
            config -- Path to a configuration file. If specified options,
                repositories etc. will be loaded from there.
            options -- List of options. Must be list of strings in a
                "key=value" format.
        """
        if cwd is None:
            if config is None:
                cwd = os.getcwd()
            else:
                cwd = os.path.abspath(os.path.dirname(config))
        self.cwd = cwd

        file_config = None
        filesystem_config = ConfigNode.from_path(self.cwd)

        # 0. config is default, but file doesn't exist, config = None
        if config == "project.xml":
            config = os.path.join(self.cwd, config)
            if not os.path.exists(config):
                config = None

        # 1. config is None: use filesystem config
        if config is None:
            if filesystem_config is None:
                file_config = ConfigNode()
            else:
                file_config = filesystem_config
        # 2. config is file: create file config and extend if with filesystem config
        elif os.path.exists(config):
            file_config = ConfigNode.from_file(config)
            if file_config is not None:
                file_config.extend_last(filesystem_config)
        # 3. config is alias: create virtual config and extend it with alias
        else:
            file_config = ConfigNode()
            file_config.filename = "command-line"
            file_config._extends["command-line"].append(config)

        self.config = file_config
        self.config.add_commandline_options(listify(options))
        self.parser = Parser(self.config)

    def _load_repositories(self, repos=None):
        self.parser.load_repositories(listrify(repos))
        self.parser.merge_repository_options()

    def _load_modules(self):
        if not self.parser._undefined_repo_options():
            self.parser.prepare_repositories()
            self.parser.merge_module_options()

    def _filter_modules(self, modules=None):
        self.parser.config.modules.extend(listify(modules))
        selected_modules = self.parser.find_modules(self.parser.config.modules)
        return self.parser.resolve_dependencies(selected_modules)

    def load(self, repos=None):
        """
        Load a list of repositories.

        Args:
            repos -- List of paths to repostiory files. Modules found
                in these repositores will be available later.
        """
        self._load_repositories(repos)
        self._load_modules()

    def validate(self, modules=None):
        """
        Generate and validate the required set of modules.

        Checks that the modules could be built, but does not generate
        the output.

        Args:
            modules -- List of modules which should be validated.

        Returns:
            List of modules required for the given modules (after
            resolving dependencies).
        """
        build_modules = self._filter_modules(modules)
        self.parser.validate_modules(build_modules)
        return build_modules

    def build(self, outpath, modules=None, simulate=False):
        """
        Build the given set of modules.

        Args:
            outpath -- Path where the output will be generated.
            modules -- List of modules which should be built. This list
                is combined with modules given in the configuration
                files.
            simulate -- If set to True simulate the build process. In
                that case no output will be generated.
        """
        build_modules = self._filter_modules(modules)
        buildlog = BuildLog(outpath)
        lbuild.environment.SIMULATE = simulate
        self.parser.build_modules(build_modules, buildlog)
        return buildlog
