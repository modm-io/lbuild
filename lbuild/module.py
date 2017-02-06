#!/usr/bin/env python3
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import shutil
import logging
import itertools

import lbuild.filter
import lbuild.option
import lbuild.repository

from . import exception

from .repository import Localpath
from .repository import LocalFileReaderFactory
from .repository import Repository

from .exception import BlobException

LOGGER = logging.getLogger('lbuild.repository')


def verify_module_name(modulename):
    """
    Verify that the given name is a valid module name.

    Raises an exception if the name is not valid.
    """
    if len(modulename.split(":")) < 2:
        raise BlobException("Modulename '{}' must contain one or more ':' as "
                            "separator between repository and module "
                            "names".format(modulename))


class ModuleBase:

    def init(self, module):
        pass

    def prepare(self, module, options):
        pass

    def build(self, env):
        pass


class OptionNameResolver:
    """
    Option name resolver for module options.
    """
    def __init__(self, repository, module, repo_options, module_options):
        self.repository = repository
        self.module = module
        self.repo_options = repo_options
        self.module_options = module_options

    def __getitem__(self, key: str):
        option_parts = key.split(":")

        try:
            depth = len(option_parts)
            if depth < 2:
                key = "{}:{}".format(self.module.fullname, key)
                return self.module_options[key].value
            if depth == 2:
                # Repository option
                repo, option = option_parts
                if repo == "":
                    key = "%s:%s" % (self.repository.name, option)

                return self.repo_options[key].value
            else:
                option_name = option_parts[-1]
                partial_module_name = option_parts[:-1]

                name = self.module.fill_partial_name(partial_module_name)
                name.append(option_name)
                key = ":".join(name)
                return self.module_options[key].value
        except KeyError:
            raise BlobException("Unknown option name '{}' in "
                                "module '{}'".format(key, self.module.fullname))

    def __repr__(self):
        # Create representation of merged module and repository options
        options = self.module_options.copy()
        options.update(self.repo_options)

        return repr(options)

    def __len__(self):
        return len(self.module_options) + len(self.repo_options)

class ModuleNameResolver:
    """
    Module name resolver for modules.
    """
    def __init__(self, repository, module, modules):
        self.repository = repository
        self.module = module
        self.modules = modules

    def __getitem__(self, key: str):
        partial_name = key.split(":")
        try:
            name = self.module.fill_partial_name(partial_name)
            key = ":".join(name)
            return self.modules[key]
        except KeyError:
            raise BlobException("Unknown module name '{}' in "
                                "repository '{}'".format(key, self.repository.name))

    def __repr__(self):
        return repr(self.modules)

    def __len__(self):
        return len(self.modules)


class Module:

    @staticmethod
    def parse_module(repository, module_filename: str):
        """
        Parse a specific module file.

        Returns:
            Module() module definition object.
        """
        try:
            modulepath = os.path.dirname(os.path.realpath(module_filename))
            with open(module_filename) as module_file:
                LOGGER.debug("Parse module_filename '%s'", module_filename)
                code = compile(module_file.read(), module_filename, 'exec')

                local = {
                    # The localpath(...) function can be used to create
                    # a local path form the folder of the repository file.
                    'localpath': Localpath(modulepath),
                    'FileReader': LocalFileReaderFactory(modulepath),
                    'listify': lbuild.filter.listify,
                    'ignore_patterns': shutil.ignore_patterns,

                    'Module': ModuleBase,

                    'StringOption': lbuild.option.Option,
                    'BooleanOption': lbuild.option.BooleanOption,
                    'NumericOption': lbuild.option.NumericOption,
                    'EnumerationOption': lbuild.option.EnumerationOption,
                }
                exec(code, local)

                module = Module(repository,
                                module_filename,
                                modulepath)

                # Get the required global functions
                module.functions = Repository.get_global_functions(local, ['init', 'prepare', 'build'])
                module.init()

                return module
        except Exception as error:
            raise BlobException("While parsing '%s': %s" % (module_filename, error))

    def __init__(self,
                 repository,
                 filename: str,
                 path: str,
                 name: str=None):
        """
        Create new module definition.

        Args:
            repository : Parent repository of the module.
            filename   : Full path of the module file.
            path       : Path to the module file. Used as base for relative
                paths during the building step of the module.
        """
        self.repository = repository
        self.filename = filename
        self.path = path

        # Parent module. May be empty
        self._parent = None
        # Full qualified name ('repository:module:submodule:...')
        self._fullname = None

        self._submodules = []

        self._name = name
        self.description = ""

        # Required functions declared in the module configuration file
        self.functions = {}

        # List of module names this module depends upon
        self.dependencies = []

        # OptionNameResolver defined in the module configuration file. These
        # options are configurable through the project configuration file.
        self.options = {}

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if self._fullname is None:
            self._name = name
        else:
            raise exception.BlobAttributeException("name")

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, name):
        """
        Set a parent for the current module.

        Modules always have a dependency on their parent modules.
        """
        if self._fullname is None:
            self._parent = name
            self.depends(":{}".format(name))
        else:
            raise exception.BlobAttributeException("name")

    @property
    def fullname(self):
        return self._fullname

    def fill_partial_name(self, partial_name):
        """
        Fill the array of the module name with the parts of the full name
        of the current module.

        Returns an array of the full name.
        """
        module_fullname_parts = self.fullname.split(":")

        # Limit length of the module name to the length of the requested
        # name
        depth = len(partial_name)
        if len(module_fullname_parts) > depth:
            module_fullname_parts = module_fullname_parts[:depth]

        # Using zip_longest restricts the name to the length of full name
        # if it is shorted than the requested module name.
        name = []
        for part, fill in itertools.zip_longest(partial_name,
                                                module_fullname_parts,
                                                fillvalue=""):
            name.append(fill if (part == "") else part)
        return name

    def init(self):
        # Execute init() function from module to get module name
        self.functions['init'](self)

        if self.name is None:
            raise BlobException("The init(module) function must set a module name! " \
                                "Please set the 'name' attribute.")

        LOGGER.info("Found module '%s'", self.name)

    def register_module(self):
        """
        Update the fullname attribute and register module at its repository.
        """
        if self._fullname is not None:
            return

        if self._parent is None:
            fullname = "{}:{}".format(self.repository.name, self._name)
        else:
            fullname = "{}:{}:{}".format(self.repository.name,
                                         self._parent,
                                         self._name)
        self._fullname = fullname
        if self.repository.modules.get(fullname, None) is not None:
            raise BlobException("Module name '{}' is not unique".format(fullname))
        self.repository.modules[fullname] = self

    def prepare(self, repo_options):
        """
        Prepare module.

        Recursively appends all submodules.
        """
        available_modules = {}
        prepare_function = self.functions["prepare"]
        name_resolver = lbuild.repository.OptionNameResolver(self.repository,
                                                             repo_options)
        is_available = prepare_function(self, name_resolver)
        if is_available:
            self.register_module()
            available_modules[self.fullname] = self

        for submodule in self._submodules:
            if isinstance(submodule, ModuleBase):
                module = Module(repository=self.repository,
                                filename=None,
                                path=self.path)

                module.functions = {
                    'init': submodule.init,
                    'prepare': submodule.prepare,
                    'build': submodule.build,
                }
                module.init()
            else:
                module = Module.parse_module(repository=self.repository,
                                             module_filename=os.path.join(self.path,
                                                                          submodule))

            # Set parent for new module
            if self._parent:
                module.parent = "{}:{}".format(self._parent, self._name)
            else:
                module.parent = self._name
            available_modules.update(module.prepare(repo_options))

        return available_modules

    def add_submodule(self, modulename):
        self._submodules.append(modulename)

    def add_option(self, option):
        """
        Define new option for this module.

        The module options only influence the build process but not the
        selection and dependencies of modules.
        """
        self._check_for_duplicates(option.name)
        option.repository = self.repository
        option.module = self
        self.options[option.name] = option

    def _check_for_duplicates(self, name):
        if name in self.options:
            raise BlobException("Option name '%s' is already defined" % name)

    def depends(self, *dependencies):
        """
        Add one or more dependencies for the module.

        Keyword arguments:
        dependencies -- one or several dependencies as comma separated arguments.
        """
        for dependency in dependencies:
            verify_module_name(dependency)
            self.dependencies.append(dependency)

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __repr__(self):
        return "Module({})".format(self.fullname)

    def __str__(self):
        return self.fullname
