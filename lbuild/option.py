#!/usr/bin/env python3
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import enum
import inspect

from .exception import BlobException

class Option:
    """
    Base class for repository and module options.

    Can be used for string based options.
    """
    def __init__(self, name, description, value=None):
        if ":" in name:
            raise BlobException("Character ':' is not allowed in options "
                                "name '{}'".format(name))

        self.name = name
        self.description = description

        # Parent repository for this option
        self.repository = None
        # Parent module. Is set to none if the option is a repository
        # option and not a module option.
        self.module = None

        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @property
    def full_name(self):
        name = []
        if self.repository is not None:
            name.append(self.repository.name)
        if self.module is not None:
            name.append(self.module.name)
        name.append(self.name)
        return ':'.join(name)

    def __lt__(self, other):
        return self.full_name.__lt__(other.full_name)

    def __str__(self):
        return "{}={}".format(self.full_name, self.value)


class BooleanOption(Option):

    def __init__(self, name, description, value=False):
        Option.__init__(self, name, description)
        if value is not None:
            self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_boolean(value)

    @staticmethod
    def as_boolean(value):
        if value is None:
            return value
        elif isinstance(value, bool):
            return value
        elif str(value).lower() in ['true', 'yes', '1']:
            return True
        elif str(value).lower() in ['false', 'no', '0']:
            return False

        raise BlobException("Value '%s' (%s) must be boolean" %
                            (value, type(value).__name__))

    def __str__(self):
        if self.value is None:
            return "{}=[True|False]".format(self.name)
        else:
            return "{}={}".format(self.full_name, self.value)


class NumericOption(Option):

    def __init__(self, name, description, value=None):
        Option.__init__(self, name, description)
        if value is not None:
            self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_numeric_value(value)

    @staticmethod
    def as_numeric_value(value):
        if value is None:
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return int(value, 0)
            except:
                pass

        raise BlobException("Value '%s' (%s) must be numeric" %
                            (value, type(value).__name__))

    def __str__(self):
        return "{}={}".format(self.full_name, self.value)


class EnumerationOption(Option):

    def __init__(self, name, description, enumeration, value=None):
        Option.__init__(self, name, description)
        if inspect.isclass(enumeration) and issubclass(enumeration, enum.Enum):
            self._enumeration = enumeration
        else:
            self._enumeration = enum.Enum(name, enumeration)
        if value is not None:
            self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_enumeration(value)

    def as_enumeration(self, value):
        try:
            # Try to access 'value' as if it where an enum
            return self._enumeration[value.name]
        except AttributeError:
            return self._enumeration[value]

    def __str__(self):
        return "{}={}".format(self.full_name, self.value)
