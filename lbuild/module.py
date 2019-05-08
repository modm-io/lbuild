
#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import logging
import inspect

import lbuild.utils
import lbuild.format

import lbuild.exception as le
import lbuild.facade as lf
from .node import BaseNode

LOGGER = logging.getLogger('lbuild.module')


class ModuleBase:
    pass


def load_module_from_file(repository, filename, parent=None):
    module = ModuleInit(repository, filename, parent)
    module.functions = lbuild.node.load_functions_from_file(
        repository,
        filename,
        required=['init', 'prepare', 'build'],
        optional=['pre_build', 'validate', 'post_build'],
        local={'PreBuildException': le.LbuildValidateException})

    module.init()
    return module.prepare()


def load_module_from_object(repository, module_obj, filename, parent=None):
    module = ModuleInit(repository, filename, parent)
    try:
        module.functions = lbuild.utils.get_global_functions(
            module_obj,
            required=['init', 'prepare', 'build'],
            optional=['pre_build', 'validate', 'post_build'])

    except le.LbuildUtilsFunctionNotFoundException as error:
        raise le.LbuildNodeMissingFunctionException(repository, filename, error, module_obj)

    module.init()
    return module.prepare()


def build_modules(initmodules):
    rmodules = {}
    modules = []
    not_available = set()
    # First convert the modules into node objects
    for initmodule in initmodules:
        if initmodule.available:
            module = Module(initmodule)
            rmodules[module.fullname] = module
            modules.append(module)
        else:
            not_available.add(initmodule.fullname)

    # then connect the entire tree
    for module in modules:
        parent_name = ":".join(module.fullname.split(":")[:-1])
        parent = rmodules.get(parent_name) if ":" in parent_name else module._repository
        if parent:
            parent.add_child(module)
        elif parent_name in not_available:
            # The parent module exists, but it is disabled and thus all its
            # children modules are disabled as well.
            module._available = False;
            not_available.add(module.fullname)
        else:
            raise le.LbuildModuleParentNotFoundException(module, parent_name)

    # Now update the tree
    if modules:
        modules[0].root._update()

    return modules


class ModuleInit:

    def __init__(self, repository, filename, parent=None):
        self.filename = os.path.realpath(filename)
        self.filepath = os.path.dirname(self.filename) if filename else None
        self.repository = repository

        self.name = None
        self.parent = None
        self.context_parent = parent
        self.description = ""
        self.functions = {}
        self.available = False
        self._format_description = lbuild.format.format_description
        self._format_short_description = lbuild.format.format_short_description

        self._submodules = []
        self._options = []
        self._dependencies = []
        self._filters = []
        self._queries = []
        self._collectors = []

    @property
    def fullname(self):
        if self.parent is None:
            return "{}:{}".format(self.repository.name, self.name)
        return "{}:{}".format(self.parent, self.name)

    def _clean(self, name):
        if name is None or not name: return ("", "");
        if name.startswith("{}:".format(self.repository.name)):
            name = name[len(self.repository.name):]
        if not name.startswith(":"):
            name = ":{}".format(name)
        return name.rsplit(":", 1)

    def init(self):
        # Execute init() function from module to get module name
        lbuild.utils.with_forward_exception(
            self,
            lambda: self.functions['init'](lf.ModuleInitFacade(self)))

        if self.name is None:
            raise le.LbuildModuleNoNameException(self)

        if self.parent is None and ":" not in self.name:
            self.parent = self.context_parent

        parent_parent, parent_name = self._clean(self.parent)
        name_parent, self.name = self._clean(self.name)

        self.parent = ":".join(p.strip(":") for p in (self.repository.name,
                                parent_parent, parent_name, name_parent) if p)

    def prepare(self):
        self.available = lbuild.utils.with_forward_exception(
            self,
            lambda: self.functions["prepare"](lf.ModulePrepareFacade(self),
                                              self.repository.option_value_resolver))

        all_modules = [self]
        if self.available is None:
            raise le.LbuildModuleNoReturnAvailableException(self)

        for submodule in self._submodules:
            if isinstance(submodule, str):
                modules = load_module_from_file(repository=self.repository,
                                                filename=os.path.join(self.filepath, submodule),
                                                parent=self.fullname)
            else:
                modules = load_module_from_object(repository=self.repository,
                                                  module_obj=submodule,
                                                  filename=self.filename,
                                                  parent=self.fullname)
            all_modules.extend(modules)
        return all_modules


class Module(BaseNode):

    def __init__(self, module: ModuleInit):
        """
        Create new module definition.

        Args:
            repository: Parent repository of the module.
            filename: Full path of the module file.
            path: Path to the module file. Used as base for relative paths
                during the building step of the module.
        """
        BaseNode.__init__(self, module.name, self.Type.MODULE, module.repository)

        self._filename = module.filename
        self._functions = module.functions
        self._description = module.description
        self._fullname = module.fullname
        self._available = module.available

        # Prefix the global filters with the `repo.` name
        for (name, func) in module._filters:
            if not name.startswith("{}.".format(self._repository.name)):
                nname = "{}.{}".format(self._repository.name, name)
                LOGGER.warning("Namespacing module filter '{}' to '{}'!"
                               .format(name, nname))
                name = nname
            self._filters[name] = func

        try:
            for child in (module._options + module._queries):
                self.add_child(child)
            for collector in module._collectors:
                self.add_child(lbuild.collector.Collector(collector))
        except le.LbuildNodeDuplicateChildException as error:
            raise le.LbuildModuleDuplicateChildException(self, error)

        dependencies = module._dependencies
        if ":" in module.parent:
            dependencies.append(module.parent)
        self.add_dependencies(*dependencies)

    def validate(self, env):
        validate = self._functions.get("validate", self._functions.get("pre_build", None))
        if validate is not None:
            LOGGER.info("Validate {}".format(self.fullname))
            lbuild.utils.with_forward_exception(self, lambda: validate(env.facade))

    def build(self, env):
        LOGGER.info("Build %s", self.fullname)
        lbuild.utils.with_forward_exception(self, lambda: self._functions["build"](env.facade))

    def post_build(self, env):
        post_build = self._functions.get("post_build", None)
        if post_build is not None:
            LOGGER.info("Post-Build {}".format(self.fullname))
            if len(inspect.signature(post_build).parameters.keys()) == 1:
                func = lambda: post_build(env.facade)
            else:
                func = lambda: post_build(env.facade, env.facade_buildlog)
            lbuild.utils.with_forward_exception(self, func)

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __repr__(self):
        return "Module({})".format(self.fullname)

    def __str__(self):
        return self.fullname
