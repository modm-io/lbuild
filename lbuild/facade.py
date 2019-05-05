#!/usr/bin/env python3
#
# Copyright (c) 2018, Niklas Hauser
# Copyright (c) 2018, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import lbuild.utils
import lbuild.filter
import warnings
import logging
import inspect
from .option import OptionSet

LOGGER = logging.getLogger('lbuild.facade')
VERBOSE_DEPRECATION = 0

def deprecated(since, function, replacement=None, obj=None):
    def pretty(function):
        if isinstance(function, str):
            return function
        cname = function.__self__.__class__ if hasattr(function, "__self__") else obj
        cname = cname.__name__.replace("Facade", "")
        fname = function.__name__
        fsig = str(inspect.signature(function))
        return "{}.{}{}".format(cname, fname, fsig)


    call_site = lbuild.exception._call_site(plain=True) if VERBOSE_DEPRECATION else ""
    msg = "{}\n'{}' is deprecated since v{}".format(call_site, pretty(function), since)
    if replacement:
        replacement = pretty(replacement)
        if "\n" in replacement:
            msg += ", use \n{}\ninstead!".format(lbuild.filter.indent(replacement, spaces=4, first_line=True))
        else:
            msg += ", use '{}' instead".format(replacement)
    msg += "!\n"
    warnings.warn(msg, DeprecationWarning)

    if VERBOSE_DEPRECATION:
        LOGGER.warning(msg)
    else:
        LOGGER.debug(msg)


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
        super().__init__(node)

    # Disable warnings caused by property setters which are not properly recognised by pylint
    # pylint: disable=no-member
    @BaseNodePrepareFacade.name.setter
    def name(self, value):
        self._node.name = value

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
        super().__init__(repository)

    def add_option(self, option):
        self._node._options.append(option)

    def add_set_option(self, option, default=None):
        self._node._options.append(OptionSet(option, default))

    def add_query(self, query):
        self._node._queries.append(query)

    def add_ignore_patterns(self, *patterns):
        self._node._ignore_patterns.extend(patterns)

    def add_filter(self, name, function):
        self._node._filters.append( (name, function,) )

    def add_configuration(self, name, path, description=None):
        self._node._configurations.append( (name, path, description,) )


class RepositoryPrepareFacade(BaseNodePrepareFacade):

    def __init__(self, repository):
        super().__init__(repository)

    def add_modules_recursive(self, basepath="", modulefile="module.lb", ignore=None):
        self._node.add_modules_recursive(basepath, modulefile, ignore)

    def add_modules(self, *modules):
        self._node.add_modules(*modules)

    def add_submodule(self, module):
        self._node.add_modules(module)

    def glob(self, pattern):
        return self._node.glob(pattern)

    # deprecated functions
    def find_modules_recursive(self, basepath="", modulefile="module.lb", ignore=None):
        deprecated("1.8.0", self.find_modules_recursive, self.add_modules_recursive)
        self.add_modules_recursive(basepath, modulefile, ignore)


class ModulePrepareFacade(BaseNodePrepareFacade):

    def __init__(self, module):
        super().__init__(module)

    @property
    def parent(self):
        return self._node.parent

    def add_option(self, option):
        self._node._options.append(option)

    def add_set_option(self, option, default=None):
        self._node._options.append(OptionSet(option, default))

    def add_query(self, query):
        self._node._queries.append(query)

    def add_collector(self, collector):
        self._node._collectors.append(collector)

    def add_modules(self, *modules):
        self._node._submodules.extend(modules)

    def add_submodule(self, module):
        self._node._submodules.append(module)

    def depends(self, *dependencies):
        self._node._dependencies.extend(dependencies)


class ModuleInitFacade(BaseNodeInitFacade):

    def __init__(self, module):
        super().__init__(module)

    @property
    def parent(self):
        deprecated("1.11.0", "ModuleInit.parent")
        return self._node.parent if self._node.parent is None else self._node.parent

    @parent.setter
    def parent(self, name):
        deprecated("1.11.0", "ModuleInit.parent = \"parent\"",
                   "module.name = \":parent:module\"")
        self._node.parent = name

    def add_filter(self, name, function):
        self._node._filters.append( (name, function,) )


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

    def has_collector(self, key):
        return key in self._env.collectors_available

    def get(self, key, default=None):
        return self._env.options.get(key, default)

    def query(self, key, default=None):
        if default is not None:
            deprecated("1.8.0", self.query,
                       "if env.has_query(key):\n"
                       "    value = env.query(key)\n"
                       "else:\n"
                       "    value = default")
            return self._env.queries.get(key, default)
        return self._env.queries[key]

    def repopath(self, *path):
        return self._env.repopath(*path)

    def localpath(self, *path):
        return self._env.modulepath(*path)

    def __getitem__(self, key):
        return self._env.options[key]

    # deprecated functions
    def get_option(self, key, default=None):
        deprecated("1.8.0", self.get_option, self.get)
        return self.get(key, default)


class EnvironmentBuildCommonFacade(EnvironmentValidateFacade):

    def __init__(self, env):
        super().__init__(env)

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
        if metadata is not None:
            deprecated("1.8.0", "EnvironmentBuild.copy(..., metadata=metadata)",
                                "operations = env.copy(...)\n"
                                "for key, values in metadata.items():\n"
                                "    env.collect(key, *values, operations=operations)")
        return self._env.copy(src, dest, ignore, metadata)

    def extract(self, archive, src=None, dest=None, ignore=None, metadata=None):
        if metadata is not None:
            deprecated("1.8.0", "EnvironmentBuild.extract(..., metadata=metadata)",
                                "operations = env.extract(...)\n"
                                "for key, values in metadata.items():\n"
                                "    env.collect(key, *values, operations=operations)")
        return self._env.extract(archive, src, dest, ignore, metadata)

    def template(self, src, dest=None, substitutions=None, filters=None, metadata=None):
        if metadata is not None:
            deprecated("1.8.0", "EnvironmentBuild.template(..., metadata=metadata)",
                                "operations = env.template(...)\n"
                                "for key, values in metadata.items():\n"
                                "    env.collect(key, *values, operations=operations)")
        return self._env.template(src, dest, substitutions, filters, metadata)

    def generated_local_files(self, filterfunc=None):
        return self._env.generated_local_files(filterfunc)

    def relative_outpath(self, path, relative_to=None):
        return self._env.reloutpath(path, relative_to)

    def real_outpath(self, path, basepath=None):
        return self._env.outpath(path, basepath=basepath)


    @staticmethod
    def ignore_files(*files):
        return lbuild.utils.ignore_files(*files)

    @staticmethod
    def ignore_paths(*paths):
        return lbuild.utils.ignore_patterns(*paths)


    # deprecated functions
    @staticmethod
    def ignore_patterns(*patterns):
        deprecated("1.8.0", EnvironmentPostBuildFacade.ignore_patterns,
                            EnvironmentPostBuildFacade.ignore_paths,
                            obj=EnvironmentPostBuildFacade)
        return EnvironmentPostBuildFacade.ignore_paths(*patterns)

    def get_generated_local_files(self, filterfunc=None):
        deprecated("1.8.0", self.get_generated_local_files, self.generated_local_files)
        return self.generated_local_files(filterfunc)

    def outpath(self, *path, basepath=None):
        deprecated("1.8.0", self.outpath, self.real_outpath)
        return self.real_outpath(os.path.join(*path), basepath=basepath)

    def reloutpath(self, path, relative=None):
        deprecated("1.8.0", self.reloutpath, self.relative_outpath)
        return self.relative_outpath(path, relative)


class EnvironmentPostBuildFacade(EnvironmentBuildCommonFacade):

    def __init__(self, env):
        super().__init__(env)

    @property
    def buildlog(self):
        return self._env.facade_buildlog

    def has_collector(self, key):
        return key in self._env.collectors

    def collector_values(self, key, default=None, filterfunc=None, unique=True):
        return self._env.collector_values(key, default, filterfunc, unique)

    def collector(self, key):
        return CollectorFacade(self._env.collectors[key])


class EnvironmentBuildFacade(EnvironmentBuildCommonFacade):

    def __init__(self, env):
        super().__init__(env)

    def collect(self, key, *values, operations=None):
        self._env.add_to_collector(key, *values, operations=operations)

    # deprecated functions
    def add_metadata(self, key, *values):
        deprecated("1.8.0", self.add_metadata, self.collect)
        self._env.add_metadata(key, *values)

    def append_metadata(self, key, *values):
        deprecated("1.8.0", self.append_metadata, self.add_metadata)
        self._env.add_metadata(key, *values)

    def append_metadata_unique(self, key, *values):
        deprecated("1.8.0", self.append_metadata_unique, self.add_metadata)
        self._env.add_metadata(key, *values)


class CollectorFacade:
    def __init__(self, collector):
        self._collector = collector

    def values(self, filterfunc=None, unique=True):
        return self._collector.values(filterfunc, unique)

    def items(self):
        return self._collector.items()

    def operations(self):
        return self._collector.keys()


class BuildLogOperationFacade:

    def __init__(self, operation):
        self._operation = operation
        self.has_filename = True

    @property
    def repository(self):
        return self.module.split(":")[0]

    @property
    def module(self):
        return self._operation.module_name

    @property
    def filename(self):
        return self._operation.local_filename_out()

    # deprecated functions
    @property
    def module_name(self):
        deprecated("1.8.0", "BuildLogOperation.module_name", "BuildLogOperation.module")
        return self.module

    def local_filename_out(self, path=None):
        deprecated("1.8.0", self.local_filename_out, "BuildLogOperation.filename")
        return self._operation.local_filename_out(path)


class BuildLogFacade:

    def __init__(self, buildlog):
        self._buildlog = buildlog

    @property
    def outpath(self):
        return self._buildlog._outpath

    @property
    def metadata(self):
        deprecated("1.8.0", "BuildLog.metadata", EnvironmentBuildFacade(None).collect)
        return self._buildlog.metadata

    @property
    def operation_metadata(self):
        deprecated("1.8.0", "BuildLog.operation_metadata", EnvironmentBuildFacade(None).collect)
        return self._buildlog.operation_metadata

    @property
    def module_metadata(self):
        deprecated("1.8.0", "BuildLog.module_metadata", EnvironmentBuildFacade(None).collect)
        return self._buildlog.module_metadata

    @property
    def repo_metadata(self):
        deprecated("1.8.0", "BuildLog.repo_metadata", EnvironmentBuildFacade(None).collect)
        return self._buildlog.repo_metadata

    @property
    def repositories(self):
        return self._buildlog.repositories

    @property
    def modules(self):
        return self._buildlog.modules

    @property
    def operations(self):
        return [BuildLogOperationFacade(operation) for operation in self._buildlog.operations]

    def operations_per_module(self, modulename: str):
        return self._buildlog.operations_per_module(modulename)

    def __iter__(self):
        return iter(self.operations)

    # deprecated
    def get_operations_per_module(self, modulename: str):
        deprecated("1.8.0", self.get_operations_per_module, self.operations_per_module)
        return self.operations_per_module(modulename)
