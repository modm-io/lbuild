#!/usr/bin/env python3
#
# Copyright (c) 2015-2016, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import textwrap
import lbuild.utils


def wordwrap(value, width=79):
    return '\n\n'.join([textwrap.fill(s, width) for s in value.split('\n\n')])


def indent(text, spaces=0, first_line=False):
    """
    Indent the text by the given number of white spaces.
    """
    prefix = ' ' * spaces
    if first_line:
        return textwrap.indent(text, prefix)

    return ("\n" + prefix).join(text.splitlines())


def pad(text, min_width, tabwidth=4):
    """
    Fill the text with tabs at the end until the minimal width is reached.
    """
    tab_count = ((min_width / tabwidth) - (len(text) / tabwidth)) + 1
    return text + ('\t' * int(tab_count))


def split(value, delimiter):
    return value.split(delimiter)


def values(dictionaries, key):
    """
    Go through the list of dictionaries and add all values of a certain key
    to a list.
    """
    value_list = []
    for item in dictionaries:
        if isinstance(item, dict) and key in item:
            if item[key] not in value_list:
                value_list.append(item[key])
    return value_list


def listify(*node):
    return lbuild.utils.listify(*node)


DEFAULT_FILTERS = {
    'lbuild.wordwrap': wordwrap,
    'lbuild.indent': indent,
    'lbuild.pad': pad,
    'lbuild.values': values,
    'lbuild.split': split,
    'lbuild.listify': listify,
}
