#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import shutil
import logging
import itertools

import lbuild.utils
import lbuild.filter
import lbuild.option
import lbuild.repository

from . import exception

from .repository import RelocatePath
from .repository import LocalFileReaderFactory
from .repository import Repository

from .exception import BlobException
from lbuild.exception import BlobForwardException

LOGGER = logging.getLogger('lbuild.module')


def verify_module_name(modulename):
    """
    Verify that the given name is a valid module name.

    Raises an exception if the name is not valid.
    """
    if len(modulename.split(":")) < 2:
        raise BlobException("Modulename '{}' must contain one or more ':' as "
                            "separator between repository and module "
                            "names".format(modulename))


def find_modules(modules, modulename):
    """ Get the module representation from a module name.

    The name can either be fully qualified, have an empty repository/module
    string or use a '*'. In the later two cases all repositories/modules are
    searched for the module name.

    It is also possible to use a double star ('**') as last entry in module
    name. In this all modules at this depth including their submodules
    are selected.

    E.g. modules "a:b", "a:c" and "a:c:d" are available. The name "a:*"
    selects "a:b" and "a:c" but not "a:c:d" while "a:**" would
    select all three.

    Args:
        modulename: Name of the module in the format
            'repository:module:submodule:...'.
            Each part but the last can be an empty string.

    Returns:
        list: Possible modules.
    """
    verify_module_name(modulename)

    canidates = []

    target_parts = modulename.split(":")
    target_depth = len(target_parts)

    if target_parts[-1] == "**":
        # Remove the double star entry
        target_parts = target_parts[:-1]

        for module in modules.values():
            parts = module.fullname.split(":")
            depth = len(parts)
            if depth >= target_depth:
                parts = parts[:target_depth]
                canidates.append((parts, module))
    else:
        for module in modules.values():
            parts = module.fullname.split(":")
            depth = len(parts)
            if depth == target_depth:
                canidates.append((parts, module))

    found = []
    for parts, module in canidates:
        for target, canidate in zip(target_parts, parts):
            if target == "" or target == "*":
                continue
            elif target != canidate:
                break
        else:
            found.append(module)

    if len(found) == 0:
        raise BlobException("Module '{}' not found.".format(modulename))
    return found


def find_module(modules, modulename):
    """
    Find a single module.

    Similar to find_modules(...) but returns only a single module and
    raised an exception in case multiple modules are found.

    Returns:
        Single module corresponding to the module name.
    """
    found = find_modules(modules, modulename)
    if len(found) > 1:
        raise BlobException("Name '{}' is ambiguous "
                            "between '{}'.".format(modulename,
                                                   "', '".join([str(x) for x in found])))
    return found[0]


def resolve_modules(available_modules, module_names):
    """
    Convert a list of not fully quailfied module names into a list of
    module objects.

    Args:
        available_modules: List of all available modules.
        module_names: List of module names.

    Returns:
        List of module objects.
    """
    selected_modules = set()
    for modulename in module_names:
        module_list = find_modules(available_modules, modulename)

        # Only add modules which are not already selected
        for module in module_list:
            selected_modules.add(module)

    return list(selected_modules)


class ModuleBase:

    def init(self, module):
        pass

    def prepare(self, module, options):
        pass

    def pre_build(self, env):
        pass

    def build(self, env):
        pass

    def post_build(self, env, log):
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
        try:
            option_parts = key.split(":")
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
        except AttributeError as error:
            raise BlobForwardException("Invalid option '{}'".format(key), error)

    def __contains__(self, key):
        try:
            _ = self.__getitem__(key)
            return True
        except:
            return False

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


class ModuleFacade:

    def __init__(self, module):
        self._module = module

    @property
    def name(self):
        return self._module.name

    @property
    def description(self):
        return self._module.description

    @property
    def parent(self):
        return self._module.parent

    def add_option(self, option):
        self._module.add_unique_option(option)

    def depends(self, *dependencies):
        """
        Add one or more dependencies for the module.

        Args:
            dependencies: One or several dependencies as comma separated arguments.
        """
        self._module.add_dependencies(*dependencies)

    def add_submodule(self, modulename):
        self._module._submodules.append(modulename)


class ModuleInitFacade(ModuleFacade):
    """
    Module API for the initialization phase of module.

    Allows to set the module name, description and parent.
    """

    def __init__(self, module):
        ModuleFacade.__init__(self, module)

    @property
    def name(self):
        return self._module.name

    @name.setter
    def name(self, value):
        self._module.name = value

    @property
    def description(self):
        return self._module.description

    @description.setter
    def description(self, value):
        self._module.description = value

    @property
    def parent(self):
        return self._module.parent

    @parent.setter
    def parent(self, name):
        """
        Set a parent for the current module.

        Modules always have a dependency on their parent modules.
        """
        self._module.parent = name


class Module:

    @staticmethod
    def parse_module_file(repository, module_filename: str):
        """
        Parse a specific module file.

        Returns:
            Module() module definition object.
        """
        try:
            modulepath = os.path.dirname(os.path.realpath(module_filename))
            repopath = os.path.realpath(repository.path)

            local = {
                # The localpath(...) function can be used to create
                # a local path form the folder of the repository file.
                'localpath': RelocatePath(modulepath),
                'repopath': RelocatePath(repopath),
                'FileReader': LocalFileReaderFactory(modulepath),
                'listify': lbuild.filter.listify,
                'ignore_patterns': shutil.ignore_patterns,

                'Module': ModuleBase,

                'StringOption': lbuild.option.Option,
                'BooleanOption': lbuild.option.BooleanOption,
                'NumericOption': lbuild.option.NumericOption,
                'EnumerationOption': lbuild.option.EnumerationOption,
                'SetOption': lbuild.option.SetOption,

                'PreBuildException': lbuild.exception.BlobPreBuildException,
            }

            LOGGER.debug("Parse module_filename '%s'", module_filename)
            local = lbuild.utils.load_module_from_file(module_filename, local)

            module = Module(repository,
                            module_filename,
                            modulepath)

            # Get the required global functions
            module.functions = Repository.get_global_functions(
                local,
                required=['init', 'prepare', 'build'],
                optional=['pre_build', 'post_build'])
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
            repository: Parent repository of the module.
            filename: Full path of the module file.
            path: Path to the module file. Used as base for relative paths
                during the building step of the module.
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
        self.__dependency_module_names = []

        # List of module objects on which this module depends. Updated
        # by calling `resovle_dependencies()`.
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
            self.add_dependencies(":{}".format(name))
        else:
            raise exception.BlobAttributeException("name")

    @property
    def fullname(self):
        return self._fullname

    def add_unique_option(self, option):
        """
        Define new option for this module.

        The module options only influence the build process but not the
        selection and dependencies of modules.
        """
        if option.name in self.options:
            raise BlobException("Option name '%s' is already defined" % option.name)
        option.repository = self.repository
        option.module = self
        self.options[option.name] = option

    def add_dependencies(self, *dependencies):
        """
        Add a new dependencies.

        The module name has not to be fully qualified.
        """
        for dependency in dependencies:
            verify_module_name(dependency)
            self.__dependency_module_names.append(dependency)

    def resolve_dependencies(self, available_modules):
        """
        Update the internal list of dependencies.

        Resolves the module names to the actual module objects.
        """
        dependencies = set()
        for dependency_name in self.__dependency_module_names:
            try:
                dependency = find_module(available_modules, dependency_name)
            except lbuild.exception.BlobException:
                raise lbuild.exception.BlobException(" Module '{}' not found, "
                                                     "required by '{}'".format(dependency_name,
                                                                               self.fullname))
            dependencies.add(dependency)

        self.dependencies = list(dependencies)

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
        lbuild.utils.with_forward_exception(self, lambda: self.functions['init'](ModuleInitFacade(self)))

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
        exisiting_module = self.repository.modules.get(fullname, None)
        if exisiting_module is not None:
            raise BlobException("Module name '{}' is not unique. "
                                "Found at {} and {}"
                                .format(fullname,
                                        os.path.join(exisiting_module.path,
                                                     exisiting_module.filename),
                                        os.path.join(self.path, self.filename)))
        self.repository.modules[fullname] = self

    def prepare(self, repo_options):
        """
        Prepare module.

        Recursively appends all submodules.
        """
        available_modules = {}
        name_resolver = lbuild.repository.OptionNameResolver(self.repository,
                                                             repo_options)
        is_available = lbuild.utils.with_forward_exception(self,
                lambda: self.functions["prepare"](ModuleFacade(self),
                                                  name_resolver))

        if is_available is None:
            raise BlobException("The prepare() function for module '{}' must "
                                "return True or False."
                                .format(self.name))
        elif is_available:
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
                module = Module.parse_module_file(repository=self.repository,
                                                  module_filename=os.path.join(self.path,
                                                                               submodule))

            # Set parent for new module
            if self._parent:
                module.parent = "{}:{}".format(self._parent, self._name)
            else:
                module.parent = self._name
            available_modules.update(module.prepare(repo_options))

        return available_modules

    def pre_build(self, env):
        pre_build = self.functions.get("pre_build", None)
        if pre_build is not None:
            LOGGER.info("Prepare for build %s", self.fullname)
            lbuild.utils.with_forward_exception(self, lambda: pre_build(env))

    def build(self, env):
        LOGGER.info("Build %s", self.fullname)
        lbuild.utils.with_forward_exception(self, lambda: self.functions["build"](env))

    def post_build(self, env, buildlog):
        post_build = self.functions.get("post_build", None)
        if post_build is not None:
            LOGGER.info("Post-Build %s", self.fullname)
            lbuild.utils.with_forward_exception(self, lambda: post_build(env, buildlog))

    def __lt__(self, other):
        """
        Compare the full name of two modules.

        Used to sort modules by their full name.
        """
        return self.fullname.__lt__(other.fullname)

    def __repr__(self):
        return "Module({})".format(self.fullname)

    def __str__(self):
        return self.fullname
