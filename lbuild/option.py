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
import textwrap

import lbuild.filter
from .exception import BlobException


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
        self._description = description

        # Parent repository for this option
        self.repository = None
        # Parent module. Is set to none if the option is a repository
        # option and not a module option.
        self.module = None

        self._value = default

    @property
    def description(self):
        try:
            return self._description.read()
        except AttributeError:
            return self._description

    @property
    def short_description(self):
        """
        Returns the wrapped first paragraph of the description.

        A paragraph is defined by non-whitespace text followed by an empty
        line.
        """
        description = self.description
        if description is not None:
            lines = description.splitlines()
            title = []
            for line in lines:
                line = line.strip()
                if line == "":
                    if len(title) > 0:
                        break
                else:
                    title.append(line)
            description = "\n".join(textwrap.wrap("\n".join(title), 80))

        return description

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @property
    def values(self):
        return "String"

    def values_hint(self):
        return self.values

    def format(self):
        values = self.values_hint()
        if self.value is None:
            return "{} = [{}]".format(self.fullname, values)
        else:
            return "{} = {}  [{}]".format(self.fullname, self._value, values)

    @property
    def fullname(self):
        name = []
        if self.module is not None:
            name.append(self.module.fullname)
        elif self.repository is not None:
            name.append(self.repository.name)

        name.append(self.name)
        return ':'.join(name)

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __str__(self):
        return self.fullname

    def factsheet(self):
        output = []
        output.append(self.fullname)
        output.append("=" * len(self.fullname))
        output.append("")
        if self.value is not None:
            output.append("Current value: {}".format(self.value))
        output.append("Possible values: {}".format(self.values_hint()))

        description = self.description.strip()
        if len(description) > 0:
            output.append("")
            output.append(description)
        return "\n".join(output)


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

    @property
    def values(self):
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

    @property
    def values(self):
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
            except ValueError:
                pass

        raise BlobException("Value '%s' (%s) must be numeric" %
                            (value, type(value).__name__))


class EnumerationOption(Option):

    LINEWITH = 120

    def __init__(self, name, description, enumeration, default=None):
        """
        Construct an enumeration option.

        Keyword arguments:
        name -- Name of the option.
        description -- Short description of the option. Can contain markdown
            markup.
        enumeration -- If `enumeration` is an enum.Enum subclass it is used
            directly, otherwise it is converted into a dictionary. During
            the conversion the names are converted to string.
        default -- Default value which is used if no value is given in the
            configuration. If the default value is not set, the build will
            fail if no value is specified.
        """
        Option.__init__(self, name, description)
        if inspect.isclass(enumeration) and issubclass(enumeration, enum.Enum):
            self.__values = enumeration
        elif isinstance(enumeration, (list, tuple, set, range)) and \
                len(enumeration) == len(set(enumeration)):
            # If the argument is a list and the items in the list are unqiue,
            # convert it so that the value of the enum equals its name.
            self.__values = {str(entry): entry for entry in enumeration}

            if default is not None:
                default = str(default)
        elif isinstance(enumeration, (dict,)):
            self.__values = enumeration
            if default is not None:
                default = str(default)
        else:
            raise BlobException("Type {} currently not supported".format(type(enumeration)))

        if default is not None:
            self.value = default

    @property
    def value(self):
        if self._value is None:
            return None
        else:
            return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_enumeration(value)

    @property
    def values(self):
        values = list(self.__values.keys())
        values.sort()
        return values

    def values_hint(self):
        return ", ".join(self.values)

    def format(self):
        name = self.fullname + " = "
        if self._value is None:
            values = self.values_hint()
            # This +1 is for the first square brackets
            output = lbuild.filter.indent(lbuild.filter.wordwrap(values,
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
            return "{}{}  [{}]".format(name, self.value, values)

    def as_enumeration(self, value):
        try:
            # Try to access 'value' as if it where an enum
            return self.__values[value.name].value
        except AttributeError:
            return self.__values[value]
