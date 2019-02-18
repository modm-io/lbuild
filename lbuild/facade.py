#!/usr/bin/env python3
#
# Copyright (c) 2018, Niklas Hauser
# Copyright (c) 2018, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import lbuild.utils


class BaseNodePrepareFacade:

    def __init__(self, node):
        self._node = node

    @property
    def name(self):
        return self._node.name

    @property
    def description(self):
        return self._node.description

    @property
    def format_description(self):
        return self._node._format_description

    @property
    def format_short_description(self):
        return self._node._format_short_description


class BaseNodeInitFacade(BaseNodePrepareFacade):

    def __init__(self, node):
        BaseNodePrepareFacade.__init__(self, node)

    # Disable warnings caused by property setters which are not properly recognised by pylint
    # pylint: disable=no-member
    @BaseNodePrepareFacade.name.setter
    def name(self, value):
        self._node.name = value
        self._node._fullname = value

    @BaseNodePrepareFacade.description.setter
    def description(self, value):
        self._node.description = value

    @BaseNodePrepareFacade.format_description.setter
    def format_description(self, formatter):
        self._node._format_description = formatter

    @BaseNodePrepareFacade.format_short_description.setter
    def format_short_description(self, formatter):
        self._node._format_short_description = formatter


class RepositoryInitFacade(BaseNodeInitFacade):

    def __init__(self, repository):
        BaseNodeInitFacade.__init__(self, repository)

    def add_option(self, option):
        self._node.add_child(option)

    def add_ignore_patterns(self, *patterns):
        self._node._ignore_patterns.extend(patterns)

    def add_filter(self, name, function):
        self._node._new_filters[name] = function

    def add_configuration(self, name, path):
        self._node._config_map[name] = path


class RepositoryPrepareFacade(BaseNodePrepareFacade):

    def __init__(self, repository):
        BaseNodePrepareFacade.__init__(self, repository)

    def add_modules_recursive(self, basepath="", modulefile="module.lb", ignore=None):
        self._node.add_modules_recursive(basepath, modulefile, ignore)

    def add_modules(self, *modules):
        self._node.add_modules(*modules)

    def add_submodule(self, module):
        self._node.add_modules(module)

    def glob(self, pattern):
        return self._node.glob(pattern)

    # deprecated
    def find_modules_recursive(self, basepath="", modulefile="module.lb", ignore=None):
        self.add_modules_recursive(basepath, modulefile, ignore)


class ModulePrepareFacade(BaseNodePrepareFacade):

    def __init__(self, module):
        BaseNodePrepareFacade.__init__(self, module)

    @property
    def parent(self):
        return self._node.parent

    def add_option(self, option):
        self._node._options.append(option)

    def add_query(self, query):
        self._node._queries.append(query)

    def add_modules(self, *modules):
        self._node._submodules.extend(modules)

    def add_submodule(self, module):
        self._node._submodules.append(module)

    def depends(self, *dependencies):
        self._node._dependencies.extend(dependencies)


class ModuleInitFacade(BaseNodeInitFacade):

    def __init__(self, module):
        BaseNodeInitFacade.__init__(self, module)

    @property
    def parent(self):
        return self._node.parent

    @parent.setter
    def parent(self, name):
        self._node.parent = name

    def add_filter(self, name, function):
        self._node._filters[name] = function


class EnvironmentValidateFacade:

    def __init__(self, env):
        self._env = env

    @property
    def log(self):
        return self._env.log

    def has_option(self, key):
        return key in self._env.options

    def has_module(self, key):
        return key in self._env.modules

    def has_query(self, key):
        return key in self._env.queries

    def get(self, key, default=None):
        return self._env.options.get(key, default)

    def query(self, key, default=None):
        return self._env.queries.get(key, default)

    def __getitem__(self, key):
        return self._env.options[key]

    # deprecated
    def get_option(self, key, default=None):
        return self.get(key, default)


class EnvironmentPostBuildFacade(EnvironmentValidateFacade):

    def __init__(self, env):
        EnvironmentValidateFacade.__init__(self, env)

    @property
    def outbasepath(self):
        return self._env.outbasepath

    @outbasepath.setter
    def outbasepath(self, path):
        self._env.outbasepath = path

    @property
    def substitutions(self):
        return self._env.substitutions

    @substitutions.setter
    def substitutions(self, substitutions):
        self._env.substitutions = substitutions

    def copy(self, src, dest=None, ignore=None, metadata=None):
        self._env.copy(src, dest, ignore, metadata)

    def extract(self, archive, src=None, dest=None, ignore=None, metadata=None):
        self._env.extract(archive, src, dest, ignore, metadata)

    def template(self, src, dest=None, substitutions=None, filters=None, metadata=None):
        self._env.template(src, dest, substitutions, filters, metadata)

    def generated_local_files(self, filterfunc=None):
        return self._env.generated_local_files(filterfunc)

    def reloutpath(self, path, relative=None):
        return self._env.reloutpath(path, relative)

    @staticmethod
    def ignore_files(*files):
        return lbuild.utils.ignore_files(*files)

    @staticmethod
    def ignore_paths(*paths):
        return lbuild.utils.ignore_patterns(*paths)

    # deprecated
    @staticmethod
    def ignore_patterns(*patterns):
        return lbuild.utils.ignore_patterns(*patterns)

    # deprecated
    def get_generated_local_files(self, filterfunc=None):
        return self.generated_local_files(filterfunc)

    # deprecated
    def outpath(self, *path, basepath=None):
        return self._env.outpath(*path, basepath=basepath)


class EnvironmentBuildFacade(EnvironmentPostBuildFacade):

    def __init__(self, env):
        EnvironmentPostBuildFacade.__init__(self, env)

    def add_metadata(self, key, *values):
        self._env.add_metadata(key, *values)

    # deprecated
    def append_metadata(self, key, *values):
        self._env.add_metadata(key, *values)

    # deprecated
    def append_metadata_unique(self, key, *values):
        self._env.add_metadata(key, *values)


class BuildLogOperationFacade:

    def __init__(self, operation):
        self._operation = operation

    @property
    def module_name(self):
        return self._operation.module_name

    def filename_out(self, path=None):
        return self._operation.local_filename_out(path)


class BuildLogFacade:

    def __init__(self, buildlog):
        self._buildlog = buildlog

        self.__metadata = buildlog.metadata
        self.__repo_metadata = buildlog.repo_metadata
        self.__module_metadata = buildlog.module_metadata
        self.__operation_metadata = buildlog.operation_metadata

    @property
    def outpath(self):
        return self._buildlog._outpath

    @property
    def metadata(self):
        return self.__metadata

    @property
    def operation_metadata(self):
        return self.__operation_metadata

    @property
    def module_metadata(self):
        return self.__module_metadata

    @property
    def repo_metadata(self):
        return self.__repo_metadata

    @property
    def repositories(self):
        return self._buildlog.repositories

    @property
    def modules(self):
        return self._buildlog.modules

    @property
    def operations(self):
        return self._buildlog.operations

    def operations_per_module(self, modulename: str):
        return self._buildlog.operations_per_module(modulename)

    def __iter__(self):
        return iter(self._buildlog.operations)

    # deprecated
    def get_operations_per_module(self, modulename: str):
        return self.operations_per_module(modulename)
