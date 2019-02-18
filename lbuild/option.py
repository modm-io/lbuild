#!/usr/bin/env python3
#
# Copyright (c) 2016-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import enum
import inspect
import collections

import lbuild.utils

from .exception import LbuildException
from .node import BaseNode
from .format import ColorWrapper as _cw


class Option(BaseNode):

    def __init__(self, name, description, default=None, dependencies=None,
                 convert_input=str, convert_output=str):
        BaseNode.__init__(self, name, BaseNode.Type.OPTION)
        self._dependency_handler = dependencies
        self._description = description
        self._in = convert_input
        self._out = convert_output
        self._input = None
        self._output = None
        self._default = None
        self._set_default(default)

    def _set_default(self, default):
        if default is not None:
            self._input = self._in(default)
            self._output = self._out(default)
            self._default = self._in(default)

    def _update_dependencies(self):
        self._dependencies_resolved = False
        if self._dependency_handler:
            self._dependency_module_names += \
                lbuild.utils.listify(self._dependency_handler(self._input))

    def _set_value(self, value):
        self._input = self._in(value)
        self._output = self._out(value)
        self._update_dependencies()

    @property
    def module(self):
        return self.parent

    @property
    def value(self):
        return self._output

    @value.setter
    def value(self, value):
        self._set_value(value)

    @property
    def values(self):
        return ["String"]

    def is_default(self):
        return self._input == self._default

    def format_value(self):
        value = str(self._input).strip()
        if value == "":
            value = '""'
        return value

    def format_values(self):
        if self.is_default() or self._default == "":
            return _cw("String")
        return _cw("String: ") + _cw(str(self._default)).wrap("underlined")


class StringOption(Option):

    def __init__(self, name, description, default=None, dependencies=None):
        Option.__init__(self, name, description, default, dependencies)


class BooleanOption(Option):

    def __init__(self, name, description, default=False, dependencies=None):
        Option.__init__(self, name, description, default, dependencies,
                        convert_input=self.as_boolean,
                        convert_output=self.as_boolean)

    @property
    def values(self):
        return ["True", "False"]

    def format_values(self):
        if self._default:
            return _cw("True").wrap("underlined") + _cw(", False")
        return _cw("True, ") + _cw("False").wrap("underlined")

    @staticmethod
    def as_boolean(value):
        if value is None:
            return value
        if isinstance(value, bool):
            return value
        if str(value).lower() in ['true', 'yes', '1']:
            return True
        if str(value).lower() in ['false', 'no', '0']:
            return False

        raise LbuildException("Value '{}' ({}) must be boolean!"
                              .format(value, type(value).__name__))


class NumericOption(Option):

    def __init__(self, name, description, minimum=None, maximum=None,
                 default=None, dependencies=None):
        Option.__init__(self, name, description, default, dependencies,
                        convert_input=str,
                        convert_output=self.as_numeric_value)
        self.minimum = minimum
        self.maximum = maximum
        if self.minimum is not None and self.maximum is not None:
            if self.minimum >= self.maximum:
                raise LbuildException("Minimum '{}' must be smaller than maximum '{}'!"
                                      .format(self.minimum, self.maximum))

    # Disable warnings caused by property setters which are not properly recognised by pylint
    # pylint: disable=no-member
    @Option.value.setter
    def value(self, value):
        numeric_value = self.as_numeric_value(value)
        if self.minimum is not None and numeric_value < self.minimum:
            raise LbuildException("Value '{}' of '{}' must be greater than '{}'"
                                  .format(numeric_value, self.fullname, self.minimum))
        if self.maximum is not None and numeric_value > self.maximum:
            raise LbuildException("Value '{}' of '{}' must be smaller than '{}'"
                                  .format(numeric_value, self.fullname, self.maximum))
        self._set_value(value)

    @property
    def values(self):
        return ["-Inf" if self.minimum is None else str(self.minimum),
                "+Inf" if self.maximum is None else str(self.maximum)]

    def format_values(self):
        minimum = _cw(self.values[0])
        maximum = _cw(self.values[1])
        if self._default is None:
            return minimum + _cw(" ... ") + maximum

        default = _cw(str(self._default)).wrap("underlined")
        if default not in (minimum, maximum):
            return minimum + _cw(" .. ") + default + _cw(" .. ") + maximum
        if maximum == default:
            return minimum + _cw(" ... ") + default
        if minimum == default:
            return default + _cw(" ... ") + maximum

        return default

    @staticmethod
    def as_numeric_value(value):
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                pass

        raise LbuildException("Value '{}' ({}) must be numeric!"
                              .format(value, type(value).__name__))


class EnumerationOption(Option):

    def __init__(self, name, description, enumeration, default=None, dependencies=None):
        Option.__init__(self, name, description, None, dependencies,
                        convert_input=self._obj_to_str,
                        convert_output=self.as_enumeration)
        if self._is_enum(enumeration):
            self._enumeration = {self._obj_to_str(entry): entry.value for entry in enumeration}
        elif isinstance(enumeration, (list, tuple, set, range)) and \
           len(enumeration) == len(set(enumeration)):
            # If the argument is a list and the items in the list are unique,
            # convert it so that the value of the enum equals its name.
            self._enumeration = {self._obj_to_str(entry): entry for entry in enumeration}
        elif isinstance(enumeration, dict):
            self._enumeration = enumeration
            for key in self._enumeration:
                if not isinstance(key, str):
                    raise LbuildException("All enumeration keys must be of type string!")
        else:
            raise LbuildException("Type {} currently not supported"
                                  .format(type(enumeration).__name__))

        self._set_default(default)

    @staticmethod
    def _is_enum(obj):
        return inspect.isclass(obj) and issubclass(obj, enum.Enum)

    @staticmethod
    def _obj_to_str(obj):
        if EnumerationOption._is_enum(obj):
            return str(obj.name)
        return str(obj).strip()

    @property
    def values(self):
        return list(map(str, self._enumeration.keys()))

    def _format_values(self):
        values = self.values
        values.sort(key=lambda v: (float(v) if v.isdigit() else 0, v))
        return values

    def format_values(self):
        values = [_cw(v).wrap("underlined") if v == self._default else _cw(v)
                  for v in self._format_values()]
        return _cw(", ").join(values)

    def as_enumeration(self, value):
        try:
            return self._enumeration[self._obj_to_str(value)]
        except KeyError:
            raise LbuildException("Value '{}' not found in enumeration '{}'. " \
                                  "Possible values are:\n'{}'."
                                  .format(self.fullname, value, "', '".join(self._enumeration)))


class SetOption(EnumerationOption):

    def __init__(self, name, description, enumeration, default=None, dependencies=None):
        EnumerationOption.__init__(self, name, description, enumeration, None, dependencies)
        self._in = self.str_to_set
        self._out = self.as_set
        self._set_default(default)

    def format_value(self):
        return "{{{}}}".format(", ".join(map(str, self._output)))

    def format_values(self):
        values = [_cw(v).wrap("underlined") if v in self._default else _cw(v)
                  for v in self._format_values()]
        return _cw(", ").join(values)

    @staticmethod
    def str_to_set(values):
        if isinstance(values, str):
            values = [v.strip() for v in values.split(",")]
        else:
            values = list(map(str, lbuild.utils.listify(values)))
        return values

    def as_set(self, values):
        values = self.str_to_set(values)
        # remove duplicates, but retain order with OrderedDict
        return [self.as_enumeration(value) for value in collections.OrderedDict.fromkeys(values)]
