#!/usr/bin/env python3
#
# Copyright (c) 2019, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from collections import defaultdict, OrderedDict

from .format import ColorWrapper as _cw
from .node import BaseNode
from .option import *
import lbuild.utils


class CollectorContext:
    def __init__(self, module, filename=None):
        self.module = module
        self.filename = filename

    @property
    def repository(self):
        return self.module.split(":")[0]

    @property
    def has_filename(self):
        return self.filename is not None


class Collector(BaseNode):

    def __init__(self, option):
        BaseNode.__init__(self, option.name, BaseNode.Type.COLLECTOR)

        self._option = option
        self._description = option._description
        self._values = OrderedDict()

    @property
    def module(self):
        return self.parent

    def add_values(self, values, module, operations=None, filename=None):
        checked_values = list()
        self._option._filename = filename
        for value in lbuild.utils.listify(values):
            self._option.value = value
            checked_values.append(self._option.value)

        if operations is not None:
            for operation in operations:
                context = CollectorContext(operation.module, operation.filename)
                self._extend_values(context, checked_values)
        else:
            self._extend_values(CollectorContext(module), checked_values)

    def _extend_values(self, context, values):
        if context not in self._values:
            self._values[context] = []
        self._values[context].extend(values)

    def values(self, default=None, filterfunc=None, unique=True):
        if filterfunc is None:
            values = [v  for vs in self._values.values()  for v in vs]
        else:
            values = []
            for context, vals in self._values.items():
                if filterfunc(context):
                    values.extend(vals)
        if unique:
            values = list(OrderedDict.fromkeys(values))
        if default is not None and not values:
            values = lbuild.utils.listify(default)
        return values

    def items(self):
        return self._values.items()

    def keys(self):
        return self._values.keys()

    @property
    def class_name(self):
        return self._option.class_name

    def format_values(self):
        return self._option.format_values()


# Inherited Options as Collectors

class StringCollector(StringOption):
    def __init__(self, name, description, validate=None):
        StringOption.__init__(self, name, description, validate=validate)


class PathCollector(PathOption):
    def __init__(self, name, description, empty_ok=False, absolute=False):
        PathOption.__init__(self, name, description, empty_ok=empty_ok, absolute=absolute)


class BooleanCollector(BooleanOption):
    def __init__(self, name, description):
        BooleanOption.__init__(self, name, description)


class NumericCollector(NumericOption):
    def __init__(self, name, description, minimum=None, maximum=None):
        NumericOption.__init__(self, name, description, minimum, maximum)


class EnumerationCollector(EnumerationOption):
    def __init__(self, name, description, enumeration):
        EnumerationOption.__init__(self, name, description, enumeration)


class CallableCollector(Option):
    def __init__(self, name, description):
        Option.__init__(self, name, description,
                        convert_input=self.as_callable,
                        convert_output=lambda f: f)

    @staticmethod
    def as_callable(func):
        if not callable(func):
            raise ValueError("Object '{}' must be callable!".format(func))
        return func

    @property
    def values(self):
        return ["Callable"]

    def format_values(self):
        return _cw("Callable")
