#!/usr/bin/env python3
#
# Copyright (c) 2016-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import enum
import inspect
import collections
import logging

import lbuild.utils

from .node import BaseNode
from .format import ColorWrapper as _cw
import lbuild.exception as le

LOGGER = logging.getLogger('lbuild.option')


class Option(BaseNode):

    def __init__(self, name, description, default=None, dependencies=None,
                 convert_input=None, convert_output=None):
        BaseNode.__init__(self, name, BaseNode.Type.OPTION)
        self._dependency_handler = dependencies
        self.description = description
        self._in = str if convert_input is None else convert_input
        self._out = str if convert_output is None else convert_output
        self._input = None
        self._output = None
        self._default = None
        self._filename = os.path.join(os.getcwd(), "dummy")
        self._set_default(default)

    def _set_default(self, default):
        if default is not None:
            self.__set_value(default)
            self._default = self._input

    def _update_dependencies(self):
        if self._dependency_handler:
            deps = lbuild.utils.listify(self._dependency_handler(self._input))
            self.parent.add_dependencies(*deps)

    def _set_value(self, value):
        self.__set_value(value)
        self._update_dependencies()

    def __set_value(self, value):
        try:
            self._input = self._in(value)
            self._output = self._out(value)
        except (TypeError, ValueError) as error:
            raise le.LbuildOptionInputException(self, value, error)

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
        return self._default is None or self._input == self._default

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

    def __init__(self, name, description, default=None, dependencies=None, validate=None):
        Option.__init__(self, name, description, None, dependencies,
                        convert_input=self._validate_string)
        self._validate = validate
        self._set_default(default)

    def _validate_string(self, value):
        value = str(value)
        if self._validate:
            self._validate(value)
        return value


class PathOption(Option):

    def __init__(self, name, description, default=None, dependencies=None, empty_ok=False, absolute=False):
        self._empty_ok = empty_ok
        self._absolute = absolute
        Option.__init__(self, name, description, default, dependencies,
                        convert_input=self._validate_path,
                        convert_output=self._relocate_path)

    def _relocate(self, path):
        return self._absolute and (self._filename is not None) and (path != "")

    def _relocate_path(self, path):
        path = str(path).strip()
        # relocate path relative to the option filepath to absolute
        if self._relocate(path):
            path = os.path.abspath(os.path.join(self._filepath, path))
        return path

    def _validate_path(self, path):
        path = str(path).strip()
        # call the path validator function
        if not self.validate(path, self._empty_ok):
            raise TypeError("Input must be a path!")
        # Relocate path to be relative to the user's perspective
        if self._relocate(path):
            path = os.path.relpath(self._relocate_path(path), os.getcwd())
        return path

    @staticmethod
    def validate(path, empty_ok=False):
        if empty_ok and len(path) == 0:
            return True
        if not lbuild.utils.is_pathname_valid(path):
            return False
        return True

    @property
    def values(self):
        return ["Path"]

    def format_value(self):
        value = str(self._input).strip()
        if value == "":
            value = "[]"
        return value

    def format_values(self):
        if self.is_default() or self._default == "":
            return _cw("Path")
        return _cw("Path: ") + _cw(str(self._default)).wrap("underlined")


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

        raise TypeError("Input must be boolean!")


class NumericOption(Option):

    def __init__(self, name, description, minimum=None, maximum=None,
                 default=None, dependencies=None):
        Option.__init__(self, name, description, default, dependencies,
                        convert_input=str,
                        convert_output=self.as_numeric_value)
        self.minimum_input = str(minimum)
        self.maximum_input = str(maximum)
        self.minimum = None
        self.maximum = None

        try:
            self.minimum = self.as_numeric_value(minimum)
        except (TypeError, ValueError) as error:
            raise le.LbuildOptionConstructionException(self,
                    "Minimum '{}' is invalid! {}".format(minimum, error))
        try:
            self.maximum = self.as_numeric_value(maximum)
        except (TypeError, ValueError) as error:
            raise le.LbuildOptionConstructionException(self,
                    "Maximum '{}' is invalid! {}".format(maximum, error))

        if self.minimum is not None and self.maximum is not None:
            if self.minimum >= self.maximum:
                raise le.LbuildOptionConstructionException(self,
                        "Minimum '{}' must be smaller than maximum '{}'!"
                            .format(self.minimum, self.maximum))

    # Disable warnings caused by property setters which are not properly recognised by pylint
    # pylint: disable=no-member
    @Option.value.setter
    def value(self, value):
        try:
            numeric_value = self.as_numeric_value(value)
            if self.minimum is not None and numeric_value < self.minimum:
                raise ValueError("Input must be greater or equal to '{}'".format(self.minimum))
            if self.maximum is not None and numeric_value > self.maximum:
                raise ValueError("Input must be smaller or equal to '{}'".format(self.maximum))
        except (TypeError, ValueError) as error:
            raise le.LbuildOptionInputException(self, value, error)
        self._set_value(value)

    @property
    def values(self):
        return ["-Inf" if self.minimum is None else self.minimum_input,
                "+Inf" if self.maximum is None else self.maximum_input]

    def format_value(self):
        value = str(self._input)
        if value != str(self._output):
            value += " ({})".format(self._output)
        return value

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
                value = eval(value)
                if isinstance(value, (int, float)):
                    return value
            except:
                pass

        raise TypeError("Input must be numeric!")


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
            for key in self._enumeration.keys():
                if not isinstance(key, str):
                    raise le.LbuildOptionConstructionException(self,
                        "All enumeration keys must be of type string, but key '{}' is of type '{}'!"
                        .format(key, type(key).__name__))
        else:
            raise le.LbuildOptionConstructionException(self,
                "Type '{}' not supported as enumeration!".format(type(enumeration).__name__))

        self._set_default(default)

    @staticmethod
    def _is_enum(obj):
        return inspect.isclass(obj) and issubclass(obj, enum.Enum)

    @staticmethod
    def _obj_to_str(obj):
        if EnumerationOption._is_enum(obj):
            return str(obj.name)
        try:
            return str(obj).strip()
        except:
            raise TypeError("Input must be a string!", obj)

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
            raise TypeError("Input must be an element of the enumeration!")

class OptionSet(Option):

    def __init__(self, option, default=None):
        if isinstance(option, (SetOption, StringOption)):
            raise le.LbuildOptionConstructionException(self, "StringOption cannot be used as a set option!")

        Option.__init__(self, option.name, option._description,
                        convert_input=self.to_set,
                        convert_output=self.as_set)
        self._option = option
        self._dependency_handler = option._dependency_handler
        if default is not None:
            self._set_default(default)
        elif not option.is_default():
            self._set_default(option._default)

    def format_value(self):
        return "{{{}}}".format(", ".join(map(str, self._input)))

    def format_values(self):
        if isinstance(self._option, EnumerationOption):
            values = [_cw(v).wrap("underlined") if v in self._default else _cw(v)
                      for v in self._option._format_values()]
            return _cw(", ").join(values)
        return self._option.format_values()

    @property
    def class_name(self):
        otype = self._option.class_name.replace("Option", "")
        return "{}SetOption".format(otype)

    def to_set(self, values):
        if isinstance(values, str):
            values = [v.strip() for v in values.split(",")]
        values = list(map(self._option._in, lbuild.utils.listify(values)))
        return values

    def as_set(self, values):
        values = self.to_set(values)
        # remove duplicates, but retain order with OrderedDict
        return [self._option._out(value) for value in collections.OrderedDict.fromkeys(values)]


class SetOption(OptionSet):
    def __init__(self, name, description, enumeration, default=None, dependencies=None):
        LOGGER.warning("'SetOption(..., default)' is deprecated since v1.8.0, please use 'module.add_set_option(EnumerationOption(...), default)!")
        OptionSet.__init__(self, EnumerationOption(name, description, enumeration, None, dependencies), default)
