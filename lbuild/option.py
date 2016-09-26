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
from . import filter

class Option:
    """
    Base class for repository and module options.

    Can be used for string based options.
    """
    def __init__(self, name, description, default=None):
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

        self._value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @staticmethod
    def values_hint():
        return "String"

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
        values = self.values_hint()
        if self.value is None:
            return "{} = [{}]".format(self.full_name, values)
        else:
            return "{} = {}  [{}]".format(self.full_name, self._value, values)


class BooleanOption(Option):

    def __init__(self, name, description, default=False):
        Option.__init__(self, name, description)
        if default is not None:
            self.value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_boolean(value)

    @staticmethod
    def values_hint():
        return "True, False"

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


class NumericOption(Option):

    def __init__(self, name, description, minimum=None, maximum=None, default=None):
        Option.__init__(self, name, description)
        
        self.minimum = minimum
        self.maximum = maximum
        
        if default is not None:
            self.value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        numeric_value = self.as_numeric_value(value)
        if self.minimum is not None and numeric_value < self.minimum:
            BlobException("Value '{}' must be smaller than '{}'".format(self.name, self.minimum))
        if self.maximum is not None and numeric_value < self.maximum:
            BlobException("Value '{}' must be greater than '{}'".format(self.name, self.maximum))
        self._value = numeric_value

    def values_hint(self):
        return "{} ... {}".format("-Inf" if self.minimum is None else str(self.minimum),
                                  "+Inf" if self.maximum is None else str(self.maximum))

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


class EnumerationOption(Option):
    
    LINEWITH = 120
    
    def __init__(self, name, description, enumeration, default=None):
        Option.__init__(self, name, description)
        if inspect.isclass(enumeration) and issubclass(enumeration, enum.Enum):
            self._enumeration = enumeration
        elif (isinstance(enumeration, list) or isinstance(enumeration, tuple)) and \
                len(enumeration) == len(set(enumeration)):
            # If the argument is a list and the items in the list are unqiue,
            # convert it so that the value of the enum equals its name.
            self._enumeration = enum.Enum(name, dict(zip(enumeration, enumeration)))
        else:
            self._enumeration = enum.Enum(name, enumeration)
        if default is not None:
            self.value = default

    @property
    def value(self):
        if self._value is None:
            return None
        else:
            return self._value.value

    @value.setter
    def value(self, value):
        self._value = self.as_enumeration(value)

    def values_hint(self):
        values = []
        for value in self._enumeration:
            values.append(value.name)
        values.sort()
        return ", ".join(values)

    def as_enumeration(self, value):
        try:
            # Try to access 'value' as if it where an enum
            return self._enumeration[value.name]
        except AttributeError:
            return self._enumeration[value]

    def __str__(self):
        name = self.full_name + " = "
        if self._value is None:
            values = self.values_hint()
            # This +1 is for the first square brackets 
            output = filter.indent(filter.wordwrap(values,
                                                   self.LINEWITH - len(name) - 1),
                                   len(name) + 1)
            return "{}[{}]".format(name, output)
        else:
            values = self.values_hint()
            # The +4 is for the spacing and the two square brackets
            overhead = len(name) + 4
            if len(values) + overhead > self.LINEWITH:
                mark = " ..."
                max_length = self.LINEWITH - overhead - len(mark)
                values = values[0:max_length] + mark
            return "{}{}  [{}]".format(name, self._value.value, values)
