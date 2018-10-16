
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
import sys
import enum
import shutil
import anytree
import logging
import textwrap
import colorful
import itertools

import lbuild.filter
from lbuild.format import format_node, format_description, format_short_description

from .exception import LbuildException, LbuildAttributeException

LOGGER = logging.getLogger('lbuild.node')


def load_functions_from_file(repository, filename: str, required, optional=None, local={}):
    try:
        localpath = os.path.dirname(os.path.realpath(filename))
        local.update({
            # The localpath(...) function can be used to create
            # a local path form the folder of the repository file.
            'localpath': RelocatePath(localpath),
            'repopath': RelocatePath(repository._filepath),
            'FileReader': LocalFileReaderFactory(localpath),
            'listify': lbuild.filter.listify,
            # 'ignore_patterns': shutil.ignore_patterns,

            'StringOption': lbuild.option.StringOption,
            'BooleanOption': lbuild.option.BooleanOption,
            'NumericOption': lbuild.option.NumericOption,
            'EnumerationOption': lbuild.option.EnumerationOption,
            'SetOption': lbuild.option.SetOption,
        })

        # LOGGER.debug("Parse filename '%s'", filename)
        local = lbuild.utils.with_forward_exception(repository,
                lambda: lbuild.utils.load_module_from_file(filename, local))
        functions = lbuild.utils.get_global_functions(local, required, optional)
        return functions

    except FileNotFoundError as error:
        raise LbuildException("Repository configuration file not found '{}'.".format(filename))

    except KeyError as error:
        raise LbuildException("Invalid repository configuration file '{}':\n"
                            " {}: {}".format(filename,
                                             error.__class__.__name__,
                                             error))

class RelocatePath:
    def __init__(self, basepath):
        self.basepath = basepath
    def __call__(self, *args):
        return os.path.join(self.basepath, *args)

class LocalFileReader:
    def __init__(self, basepath, filename):
        self.basepath = basepath
        self.filename = filename
    def __str__(self):
        return self.read()
    def read(self):
        with open(os.path.join(self.basepath, self.filename)) as file:
            return file.read()

class LocalFileReaderFactory:
    def __init__(self, basepath):
        self.basepath = basepath
    def __call__(self, filename):
        return LocalFileReader(self.basepath, filename)

class Renderer(anytree.RenderTree):
    def __init__(self, node):
        anytree.RenderTree.__init__(self, node,
                                    style=anytree.ContRoundStyle(),
                                    childiter=self.childsort)

    def __str__(self):
        lines = [pre + format_node(node, pre) for pre, _, node in self]
        return "\n".join(lines)

    @staticmethod
    def childsort(items):
        def sorting(item):
            return (item._type != BaseNode.Type.OPTION, item.name)
        return sorted(items, key=sorting)


class NameResolver:
    """
    Name resolver for node.
    """

    def __init__(self, node, nodetype, selected=True):
        self._node = node
        self._type = nodetype
        self._str = nodetype.name.lower()
        self._value_resolver = False
        self._selected = selected

    def __getitem__(self, key: str):
        node = self._node._resolve_partial_max(key, max_results=1)[0]
        if not node._available:
            raise LbuildException("{} '{}' is not available!".format(self._str, node.fullname))
        if self._selected and not node._selected:
            raise LbuildException("{} '{}' is not selected!".format(self._str, node.fullname))
        if node._type != self._type:
            raise LbuildException("'{}' is of type '{}', but searching for '{}'!".format(
                                  node.fullname, node._type.name.lower(), self._str))
        if node._type == BaseNode.Type.OPTION and self._value_resolver:
            return node.value
        return node

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except:
            return default

    def __contains__(self, key):
        try:
            _ = self.__getitem__(key)
            return True
        except:
            return False

    def __len__(self):
        return len(self._node._findall(self._type, selected=self._selected))

    def __repr__(self):
        return repr(self._node._findall(self._type, selected=self._selected))


class BaseNode(anytree.Node):
    separator = ":"
    resolver = anytree.Resolver()

    class Type(enum.Enum):
        PARSER = 1
        REPOSITORY = 2
        MODULE = 3
        OPTION = 4

    def __init__(self, name, node_type, repository=None):
        anytree.Node.__init__(self, name)
        self._type = node_type
        self._functions = {}

        self._fullname = name
        self._filename = None

        # Dependency management
        self._repository = repository
        self._dependency_module_names = []
        self._dependencies_resolved = False
        self._dependencies = []

        self._description = ""
        # All _update()-able traits: defaults
        self._available_default = True
        self._selected_default = True
        self._format_description_default = format_description
        self._format_short_description_default = format_short_description
        self._context_default = None

        # All _update()-able traits: defaults
        self._available = (self._type != BaseNode.Type.MODULE)
        self._selected = True
        self._format_description = self._format_description_default
        self._format_short_description = self._format_short_description_default
        self._context = self._context_default
        self._ignore_patterns = lbuild.utils.default_ignore_patterns
        self._filters = lbuild.filter.default_filters

    @property
    def format_description(self):
        return format_description

    @property
    def format_short_description(self):
        return format_short_description

    @property
    def _filepath(self):
        return os.path.dirname(self._filename)

    @property
    def fullname(self):
        if self._fullname is None:
            self._fullname = self.name
        return self._fullname

    @property
    def type(self):
        return self._type

    @property
    def options(self):
        return self.all_options(depth=2)

    @property
    def submodules(self):
        return self.all_modules(depth=2)

    @property
    def repository(self):
        return self._repository

    @property
    def dependencies(self):
        if not self._dependencies_resolved:
            self._resolve_dependencies()
        return self._dependencies + [d for o in self.all_options(depth=2) for d in o._dependencies if d != self]

    @property
    def description(self):
        return self._format_description(self, str(self._description))

    @property
    def short_description(self):
        return self._format_short_description(self, str(self._description))

    @description.setter
    def description(self, description):
        self._description = description

    @property
    def option_value_resolver(self):
        resolver = NameResolver(self, self.Type.OPTION)
        resolver._value_resolver = True
        return resolver

    @property
    def option_resolver(self):
        return NameResolver(self, self.Type.OPTION)

    @property
    def module_resolver(self):
        return NameResolver(self, self.Type.MODULE)

    def render(self):
        return Renderer(self)

    def add_dependencies(self, *dependencies):
        """
        Add a new dependencies.

        The module name has not to be fully qualified.
        """
        self._dependency_module_names += dependencies

    def add_option(self, option):
        """
        Define new option for this module.

        The module options only influence the build process but not the
        selection and dependencies of modules.
        """
        if option.name in [c.name for c in self.children]:
            raise LbuildException("Option name '{}' is already defined".format(option.name))
        option._repository = self._repository
        option.parent = self
        option.add_dependencies(self.fullname)
        option._fullname = self.fullname + ":" + option.name

    def all_options(self, depth=None, selected=True):
        return self._findall(self.Type.OPTION, depth, selected)

    def all_modules(self, depth=None, selected=True):
        return self._findall(self.Type.MODULE, depth, selected)

    def _findall(self, node_type, depth=None, selected=True):
        def _filter(n):
            return (n._type == node_type and
                    n._available and
                    (n._selected or not selected) and
                    n is not self)
        return anytree.search.findall(self, maxlevel=depth, filter_=_filter)

    def _resolve_dependencies(self, ignore_failure=False):
        """
        Update the internal list of dependencies.

        Resolves the module names to the actual module objects.
        """
        if self._dependencies_resolved:
            return
        dependencies = set()
        # print(self.fullname, self._dependency_module_names)
        dependency_names = set(n for n in self._dependency_module_names if ":" in n)
        for dependency_name in dependency_names:
            try:
                dependencies.add(self.module_resolver[dependency_name])
            except LbuildException as b:
                if not ignore_failure:
                    raise LbuildException("Cannot resolve dependencies!\n" + str(b))
                LOGGER.debug("ignoring", dependency_name)
        self._dependencies = list(dependencies)
        self._dependencies_resolved = not ignore_failure
        for child in self.children:
            child._resolve_dependencies(ignore_failure)

    def _resolve_partial_max(self, query, max_results=1):
        nodes = self._resolve_partial(query, None)
        if nodes is None:
            raise LbuildException("Unknown '{}' in module '{}'!".format(query, self.fullname))
        if len(nodes) > max_results:
            raise LbuildException("Ambiguous '{}'! Found: '{}'".format(query, "', '".join([n.fullname for n in nodes])))
        return nodes

    def _resolve_partial(self, query, default=[]):
        # Try if query result is unique
        resolved1 = self._resolve(query, [])
        if len(resolved1) == 1:
            return resolved1
        # no result or ambiguous? try to fill the partial name
        query = ":".join(self._fill_partial_name(["" if p == "*" else p for p in query.split(":")]))
        resolved2 = self._resolve(query, [])
        if not (len(resolved2) or len(resolved1)):
            return default # neither found anything
        if not len(resolved2):
            return resolved1
        if not len(resolved1):
            return resolved2
        # return the less ambiguous one
        return resolved2 if len(resolved2) < len(resolved1) else resolved1

    def _resolve(self, query, default=[]):
        # :*   -> non-recursive
        # :**  -> recursive
        query = ":".join(p if len(p) else "*" for p in query.strip().split(":"))
        try:
            qquery = ":" + query.replace(":**", "")
            if self.root._type == self.Type.PARSER:
                qquery = ":lbuild" + qquery
            # print("\n\n\n", qquery)
            found_modules = BaseNode.resolver.glob(self.root, qquery)
        except (anytree.resolver.ChildResolverError, anytree.resolver.ResolverError):
            return default
        modules = found_modules
        if query.endswith(":**"):
            for module in found_modules:
                modules.extend(module.descendants)
        # print("\n\n\n", modules)
        return modules if len(modules) else default

    def _fill_partial_name(self, partial_name):
        """
        Fill the array of the module name with the parts of the full name
        of the current module.

        Returns an array of the full name.
        """
        module_fullname_parts = self.fullname.split(":")

        # if partial_name is just leaf name, set scope to local node
        if len(partial_name) == 1:
            partial_name = module_fullname_parts + partial_name
        # Limit length of the module name to the length of the requested name
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

    def _update_attribute(self, attr):
        self_attr = getattr(self, attr, "unknown")
        parent_attr = getattr(self.parent, attr, "unknown")
        if self_attr is "unknown" or parent_attr is "unknown":
            raise LbuildException("Cannot update non-existant attribute '{}'!".format(attr))

        if isinstance(self_attr, list):
            self_attr = list(set(self_attr + parent_attr))
            return
        if isinstance(self_attr, dict):
            self_attr.update(parent_attr)
            return

        default = getattr(self, attr + "_default")
        if ((parent_attr is not default) and (self_attr is default)):
            setattr(self, attr, parent_attr)
            # print("Updating {}.{} = {} -> {}.".format(self.fullname, attr, self_attr, parent_attr))

    def _update_format(self):
        if self.parent:
            self._update_attribute("_format_description")
            self._update_attribute("_format_short_description")
        for c in self.children:
            c._update_format()

    def _update(self):
        if self.parent:
            self._update_attribute("_format_description")
            self._update_attribute("_format_short_description")
            self._update_attribute("_available")
            self._update_attribute("_selected")
            self._update_attribute("_ignore_patterns")
            self._update_attribute("_filters")
            self._update_attribute("_context")
        for c in self.children:
            c._update()

    def _relocate_relative_path(self, path):
        """
        Relocate relative paths to the path of the repository
        configuration file.
        """
        if not os.path.isabs(path):
            path = os.path.join(self._filepath, path)
        return os.path.normpath(path)
