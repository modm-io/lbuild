
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
import itertools

import lbuild.utils
import lbuild.filter
import lbuild.option
import lbuild.repository

from . import exception

from .repository import Repository

from .exception import LbuildException
from .exception import LbuildForwardException

from .node import BaseNode
from .facade import ModuleInitFacade, ModulePrepareFacade

LOGGER = logging.getLogger('lbuild.module')


class ModuleBase:
    pass


def load_module_from_file(repository, filename, parent=None):
    module = ModuleInit(repository, filename)
    if parent: module.parent = parent;
    module.functions = lbuild.node.load_functions_from_file(
        repository, filename,
        required=['init', 'prepare', 'build'],
        optional=['pre_build', 'validate', 'post_build'],
        local={
            'Module': ModuleBase,
            'PreBuildException': lbuild.exception.LbuildValidateException,
            'ValidateException': lbuild.exception.LbuildValidateException,
        })
    module.init()
    return module.prepare()


def load_module_from_object(repository, module_obj, filename=None, parent=None):
    module = ModuleInit(repository, filename)
    if parent: module.parent = parent;
    module.functions = lbuild.utils.get_global_functions(module_obj,
            required=['init', 'prepare', 'build'],
            optional=['pre_build', 'validate', 'post_build'])
    module.init()
    return module.prepare()


def build_modules(initmodules):
    rmodules = {}
    modules = []
    # First convert the modules into node objects
    for initmodule in initmodules:
        module = Module(initmodule)
        rmodules[module.fullname] = module
        modules.append(module)

    # then connect the entire tree
    for module in modules:
        parent = ":".join(module.fullname.split(":")[:-1])
        module.parent = rmodules[parent] if ":" in parent else module._repository

    # Now update the tree
    for module in modules:
        module._update()

    return modules


class ModuleInit:
    def __init__(self, repository, filename=None):
        self.filename = os.path.realpath(filename)
        self.filepath = os.path.dirname(self.filename) if filename else None
        self.repository = repository

        self.name = None
        self.parent = self.repository.name
        self.description = ""
        self.functions = {}
        self.available = False

        self._submodules = []
        self._options = []
        self._dependencies = []
        self._filters = {}

    @property
    def fullname(self):
        return self.parent + ":" + self.name

    def init(self):
        # Execute init() function from module to get module name
        lbuild.utils.with_forward_exception(self, lambda: self.functions['init'](ModuleInitFacade(self)))

        if self.name is None:
            raise LbuildException("The init(module) function must set a module name! " \
                                "Please set the 'name' attribute.")

        if self.parent.startswith(":"):
            self.parent = self.repository.name + self.parent
        if not self.parent.startswith(self.repository.name):
            self.parent = self.repository.name + ":" + self.parent

    def prepare(self):
        is_available = lbuild.utils.with_forward_exception(self,
                lambda: self.functions["prepare"](ModulePrepareFacade(self), self.repository.option_value_resolver))

        available_modules = []
        if is_available is None:
            raise LbuildException("The prepare() function for module '{}' must "
                                "return True or False."
                                .format(self.name))
        elif is_available:
            available_modules.append(self)
        self.available = is_available

        for submodule in self._submodules:
            if isinstance(submodule, ModuleBase):
                modules = load_module_from_object(repository=self.repository,
                                                  module_obj=submodule,
                                                  filename=self.filename,
                                                  parent=self.fullname)
            else:
                modules = load_module_from_file(repository=self.repository,
                                                filename=os.path.join(self.filepath, submodule),
                                                parent=self.fullname)

            available_modules.extend(modules)

        return available_modules


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
        self._filters.update({self._repository.name + "." + name: func for name, func in module._filters.items()})

        # OptionNameResolver defined in the module configuration file. These
        # options are configurable through the project configuration file.
        for o in module._options:
            self.add_option(o)

        self.add_dependencies(*module._dependencies)
        if ":" in module.parent:
            self.add_dependencies(module.parent)

    def validate(self, env):
        validate = self._functions.get("validate", self._functions.get("pre_build", None))
        if validate is not None:
            LOGGER.info("Validate " + self.fullname)
            lbuild.utils.with_forward_exception(self, lambda: validate(env))

    def build(self, env):
        LOGGER.info("Build " + self.fullname)
        lbuild.utils.with_forward_exception(self, lambda: self._functions["build"](env))

    def post_build(self, env, buildlog):
        post_build = self._functions.get("post_build", None)
        if post_build is not None:
            LOGGER.info("Post-Build " + self.fullname)
            lbuild.utils.with_forward_exception(self, lambda: post_build(env, buildlog))

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __repr__(self):
        return "Module({})".format(self.fullname)

    def __str__(self):
        return self.fullname
