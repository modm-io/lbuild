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
import enum
import os.path
import random
import logging
import collections

import lbuild.module
import lbuild.environment

import lbuild.exception as le

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
            self.env.stage = Parser.Stage.VALIDATE
            self.node.validate(self.env)

    def build(self):
        self.env.stage = Parser.Stage.BUILD
        self.node.build(self.env)

    def post_build(self, buildlog):
        if hasattr(self.node, "post_build"):
            self.env.stage = Parser.Stage.POST_BUILD
            self.node.post_build(self.env)


class Parser(BaseNode):

    @enum.unique
    class Stage(enum.IntEnum):
        """This order of repo/module function calls"""
        INIT = 1
        PREPARE = 2
        VALIDATE = 3
        BUILD = 4
        POST_BUILD = 5

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

        while True:
            # flatten configuration and collect repositories
            self._config_flat = self._config.flatten()
            repofiles = (repofiles | set(self._config_flat.repositories)) - parsed
            if not len(repofiles) + len(parsed):
                raise le.LbuildConfigNoReposException(self)
            parsed |= repofiles

            # Parse only new repositories
            for repofile in repofiles:
                repo = self.parse_repository(repofile)

            # nothing more to extend
            if not self._config_flat._extends:
                break

            for filename, aliases in self._config_flat._extends.items():
                node = self._config.find(filename)
                for alias in aliases:
                    fconfig = self.find_any(alias, types=BaseNode.Type.CONFIG)
                    if not fconfig:
                        raise le.LbuildConfigAliasNotFoundException(self, alias)
                    if len(fconfig) > 1:
                        raise le.LbuildConfigAliasAmbiguousException(self, alias, fconfig)
                    self._config.extend(node, ConfigNode.from_file(fconfig[0]._config))
                node._extends.pop(filename)

        self._update_format()
        LOGGER.info("\n%s", self._config.render())
        return self._config_flat

    def parse_repository(self, repofilename: str) -> repository.Repository:
        """
        Parse the given repository file.

        Executes the 'prepare' function to populate the repository
        structure.
        """
        repo = repository.load_repository_from_file(self, repofilename)
        conflict = next((c for c in self.children if c.name == repo.name), None)
        if conflict is not None:
            raise le.LbuildParserDuplicateRepoException(self, repo, conflict)
        repo.parent = self

        return repo

    def merge_repository_options(self):
        # only deal with repo options that contain one `:`
        resolver = self.option_resolver
        # print(self.config.options.items())
        for name, (value, filename) in filter(lambda i: i[0].count(":") == 1,
                                              self.config.options.items()):
            try:
                option = resolver[name]
                option._filename = filename
                option.value = value
            except le.LbuildOptionException as error:
                raise le.LbuildDumpConfigException(
                    "Failed to validate repository options!\n{}".format(error), self)
            except le.LbuildResolverNoMatchException as error:
                raise le.LbuildParserNodeNotFoundException(self, name, self.Type.OPTION)


    def prepare_repositories(self):
        undefined = self._undefined_repo_options()
        if undefined:
            raise le.LbuildOptionRequiredInputsException(undefined)

        modules = []
        for repo in self._findall(BaseNode.Type.REPOSITORY):
            moduleinits = repo.prepare()
            if not moduleinits:
                raise le.LbuildParserRepositoryEmptyException(repo)
            modules.extend(moduleinits)

        try:
            modules = lbuild.module.build_modules(modules)
        except le.LbuildNodeDuplicateChildException as error:
            raise le.LbuildParserDuplicateModuleException(self, error)
        # Update the formatters now from repo to the module leaves
        self._update_format()
        return modules

    def merge_module_options(self):
        # only deal with repo options that contain one `:`
        resolver = self.option_resolver
        for name, (value, filename) in filter(lambda i: i[0].count(":") > 1,
                                              self.config.options.items()):
            try:
                option = resolver[name]
                option._filename = filename
                option.value = value
            except le.LbuildOptionException as error:
                raise le.LbuildDumpConfigException(
                    "Failed to validate module options!\n{}".format(error), self)
            except le.LbuildResolverNoMatchException as error:
                raise le.LbuildParserNodeNotFoundException(self, name, self.Type.OPTION)

    def resolve_dependencies(self, requested_modules, depth=sys.maxsize):
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
        selected_modules = set(requested_modules.copy())

        LOGGER.info("Selected modules: %s",
                    ", ".join(sorted(module.fullname for module in selected_modules)))

        try:
            current = selected_modules
            while depth > 0:
                additional = set()
                for module in current:
                    for dependency in module.dependencies:
                        if dependency not in selected_modules and dependency not in additional:
                            LOGGER.debug("Adding dependency: %s", dependency.fullname)
                            additional.add(dependency)
                if not additional:
                    # Abort if no new dependencies are being found
                    break
                selected_modules.update(additional)
                current = additional
                additional = []
                depth -= 1

        except (le.LbuildResolverNoMatchException,
                le.LbuildResolverAmbiguousMatchException) as error:
            raise le.LbuildParserCannotResolveDependencyException(self, error)

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
                raise le.LbuildParserNodeNotFoundException(self, query, types)
            nodes |= set(result)
        if types:
            types = utils.listify(types)
            nodes = [n for n in nodes if any(n.type == t for t in types)]
        return list(nodes)

    @staticmethod
    def _undefined_options(options):
        return {o for o in options if o.value is None}

    def _undefined_repo_options(self):
        return self._undefined_options(self.repo_options.values())

    def validate_modules(self, build_modules):
        self.build_modules(build_modules, None)

    def build_modules(self, build_modules, buildlog):
        undefined = self._undefined_options(self.all_options())
        if undefined:
            raise le.LbuildOptionRequiredInputsException(undefined)
        if not build_modules:
            raise le.LbuildConfigNoModulesException(self)

        groups = collections.defaultdict(list)
        # Build environments for all modules and repos
        for node in (build_modules | {m.repository for m in build_modules}):
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
                except le.LbuildException as error:
                    exceptions.append(error)

        if exceptions:
            raise le.LbuildAggregateException(exceptions)

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
