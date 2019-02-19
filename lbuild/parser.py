#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import sys
import os.path
import random
import logging
import collections

import lbuild.module
import lbuild.environment

from .exception import LbuildException
from .exception import LbuildBuildException

from .node import BaseNode
from .config import ConfigNode
from .facade import BuildLogFacade

from . import repository
from . import utils

LOGGER = logging.getLogger('lbuild.parser')


class Runner:

    def __init__(self, node, env):
        self.node = node
        self.env = env

    def validate(self):
        if hasattr(self.node, "validate"):
            self.node.validate(self.env.facade_validate)

    def build(self):
        self.node.build(self.env.facade_build)

    def post_build(self, buildlog):
        if hasattr(self.node, "post_build"):
            self.node.post_build(self.env.facade_post_build, BuildLogFacade(buildlog))


class Parser(BaseNode):

    def __init__(self, config=None):
        BaseNode.__init__(self, "lbuild", BaseNode.Type.PARSER)
        self._config = config if config else ConfigNode()
        self._config_flat = self._config.flatten()

    @property
    def config(self):
        return self._config_flat

    @property
    def modules(self):
        return {m.fullname:m for m in self.all_modules()}

    @property
    def repositories(self):
        return {r.fullname:r for r in self._findall(BaseNode.Type.REPOSITORY)}

    @property
    def repo_options(self):
        return {o.fullname:o for o in self.all_options(depth=3)}

    @property
    def module_options(self):
        return {o.fullname:o for o in self.all_options() if o.depth > 2}

    def load_repositories(self, repofilenames=None):
        repofiles = set(os.path.realpath(p) for p in utils.listify(repofilenames))
        parsed = set()
        config_map = {}

        while True:
            # flatten configuration and collect repositories
            self._config_flat = self._config.flatten()
            repofiles = (repofiles | set(self._config_flat.repositories)) - parsed
            if not len(repofiles) + len(parsed):
                LOGGER.error("\n%s", self._config.render())
                raise LbuildException("No repositories loaded!")
            parsed |= repofiles

            # Parse only new repositories
            for repofile in repofiles:
                repo = self.parse_repository(repofile)
                config_map.update({c.fullname:c._config for c in repo.configurations})

            # nothing more to extend
            if not self._config_flat._extends:
                break

            for filename, aliases in self._config_flat._extends.items():
                node = self._config.find(filename)
                for alias in aliases:
                    if alias not in config_map:
                        raise LbuildException("Configuration alias '{}' not found in any map! "
                                              "Available aliases: '{}'"
                                              .format(alias,
                                                      "', '".join(config_map)))
                    self._config.extend(node, ConfigNode.from_file(config_map[alias]))
                del node._extends[filename]

        self._update_format()
        LOGGER.info("\n%s", self._config.render())
        return self._config_flat

    def parse_repository(self, repofilename: str) -> repository.Repository:
        """
        Parse the given repository file.

        Executes the 'prepare' function to populate the repository
        structure.
        """
        repo = repository.Repository.parse_repository(repofilename)
        if repo.name in [_cw.name for _cw in self.children]:
            raise LbuildException("Repository name '{}' is ambiguous. Name must be unique."
                                  .format(repo.name))
        repo.parent = self

        return repo

    def merge_repository_options(self):
        # only deal with repo options that contain one `:`
        resolver = self.option_resolver
        for name, value in {n: v for n, v in self.config.options.items()
                            if n.count(":") == 1}.items():
            try:
                resolver[name].value = value
            except LbuildException as error:
                raise LbuildException("Failed to merge repository options!\n{}".format(error))

    def prepare_repositories(self):
        undefined = self._undefined_repo_options()
        if undefined:
            raise LbuildException("Unknown values for options '{}'. Please provide a value in the "
                                  "configuration file or on the command line."
                                  .format("', '".join(undefined)))
        modules = []
        for repo in self._findall(BaseNode.Type.REPOSITORY):
            modules.extend(repo.prepare())

        modules = lbuild.module.build_modules(modules)
        if not modules:
            raise LbuildBuildException("No module found with the selected repository options!")

        self._resolve_dependencies(ignore_failure=True)
        self._update_format()
        return modules

    def merge_module_options(self):
        # only deal with repo options that contain one `:`
        resolver = self.option_resolver
        for name, value in {n: v for n, v in self.config.options.items()
                            if n.count(":") > 1}.items():
            try:
                resolver[name].value = value
            except LbuildException as error:
                raise LbuildException("Failed to merge module options!\n{}".format(error))

    def resolve_dependencies(self, requested_modules, depth=sys.maxsize):
        # map the dependency names to the node objects
        self._resolve_dependencies()
        return self._filter_dependencies(requested_modules, depth)

    def _filter_dependencies(self, requested_modules, depth=sys.maxsize):
        """
        Resolve dependencies by adding missing modules.

        Args:
            modules (list): All modules available in the system
            requested_modules (list): Selected modules. Sub-set of all modules.
            depth (int): Maximum depth of dependencies. If not set to maximum
                not all dependencies might be resolved.

        Returns:
            list: Required modules for the given list of modules.
        """
        selected_modules = requested_modules.copy()

        LOGGER.info("Selected modules: %s",
                    ", ".join(sorted([module.fullname for module in selected_modules])))

        current = selected_modules
        while depth > 0:
            additional = []
            for module in current:
                for dependency in module.dependencies:
                    if dependency not in selected_modules and dependency not in additional:
                        LOGGER.debug("Add dependency: %s", dependency.fullname)
                        additional.append(dependency)
            if not additional:
                # Abort if no new dependencies are being found
                break
            selected_modules.extend(additional)
            current = additional
            additional = []
            depth -= 1

        # disable all non-selected modules
        for module in self.all_modules():
            if module._available:
                module._selected = module in selected_modules

        self._update()

        return selected_modules

    def find_module(self, name):
        return self.module_resolver[name]

    def find_option(self, name):
        return self.option_resolver[name]

    def find_modules(self, queries):
        return self.find_any(queries, self.Type.MODULE)

    def find_all(self, queries):
        return [node for q in utils.listify(queries) for node in self.find_any(q)]

    def find_any(self, queries, types=None):
        nodes = set()
        for query in utils.listify(queries):
            result = self._resolve_partial(query, None)
            if result is None:
                raise LbuildException("Cannot resolve '{}'".format(query))
            nodes |= set(result)
        if types:
            types = utils.listify(types)
            nodes = [n for n in nodes if any(n.type == t for t in types)]
        return list(nodes)

    @staticmethod
    def _undefined_options(options):
        undefined = []
        for fullname, option in options.items():
            if option.value is None:
                undefined.append(fullname)
        return undefined

    def _undefined_repo_options(self):
        return self._undefined_options(self.repo_options)

    @staticmethod
    def validate_modules(build_modules):
        Parser.build_modules(build_modules, None)

    @staticmethod
    def build_modules(build_modules, buildlog):
        if not build_modules:
            raise LbuildException("No modules selected, aborting!")

        groups = collections.defaultdict(list)
        for node in build_modules + list(set(m.repository for m in build_modules)):
            env = lbuild.environment.Environment(node, buildlog)
            groups[node.depth].append(Runner(node, env))

        exceptions = []
        # Enforce that the submodules are always build before their
        # parent modules.
        for index in sorted(groups, reverse=True):
            group = groups[index]
            random.shuffle(group)

            for runner in group:
                try:
                    runner.validate()
                except lbuild.exception.LbuildValidateException as error:
                    exceptions.append(error)

        if exceptions:
            raise lbuild.exception.LbuildAggregateException(exceptions)

        # Cannot build with these settings, just pre_build
        if buildlog is None:
            return

        for index in sorted(groups, reverse=True):
            group = groups[index]
            random.shuffle(group)

            for runner in group:
                runner.build()

        for index in sorted(groups, reverse=True):
            group = groups[index]
            random.shuffle(group)

            for runner in group:
                runner.post_build(buildlog)
