#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import lbuild.option

from . import utils
from .repository import Repository

from .exception import BlobException
from .exception import OptionFormatException

def verify_module_name(modulename):
    """
    Verify that the given name is a valid module name.

    Raises an exception if the name is not valid.
    """
    if len(modulename.split(":")) != 2:
        raise BlobException("Modulename '%s' must contain exactly one ':' as "
                            "separator between repository and module name" % modulename)


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
            if len(option_parts) == 2:
                # Repository option
                repo, option = option_parts
                if repo == "":
                    key = "%s:%s" % (self.repository.name, option)

                return self.repo_options[key].value
            elif len(option_parts) == 3:
                # Module option
                repo, module, option = option_parts

                if repo == "":
                    repo = self.repository.name
                if module == "":
                    module = self.module.name

                key = "%s:%s:%s" % (repo, module, option)
                return self.module_options[key].value
            else:
                raise OptionFormatException(key)

        except KeyError:
            raise BlobException("Unknown option name '%s'" % key)

    def __repr__(self):
        # Create representation of merged module and repository options
        o = self.module_options.copy()
        o.update(self.repo_options)

        return repr(o)

    def __len__(self):
        return len(self.module_options) + len(self.repo_options)


class Module:

    def __init__(self,
                 repository: Repository,
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

        if name is None:
            # Module name without repository
            self._name = None
            # Full qualified name ('repository:module')
            self.full_name = None
        else:
            self.name = name
        self.description = ""

        # Required functions declared in the module configuration file
        self.functions = {}

        # List of module names this module depends upon
        self.dependencies = []

        # OptionNameResolver defined in the module configuration file. These options are
        # configurable through the project configuration file.
        self.options = {}

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        self.full_name = "%s:%s" % (self.repository.name, name)

    # FIXME remove
    def set_name(self, name):
        self.name = name

    # FIXME remove
    def set_description(self, description):
        self.description = description

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

    def depends(self, dependencies):
        """
        Add one or more dependencies for the module.

        Keyword arguments:
        dependencies -- Either one module name or a list of module names.
        """
        for dependency in utils.listify(dependencies):
            verify_module_name(dependency)
            self.dependencies.append(dependency)

    def __lt__(self, other):
        return self.full_name.__lt__(other.full_name)

    def __repr__(self):
        return "Module({})".format(self.full_name)

    def __str__(self):
        return self.full_name
