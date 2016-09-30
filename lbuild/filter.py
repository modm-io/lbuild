#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import textwrap

TAB_WIDTH = 4


def wordwrap(value, width=79):
    return '\n\n'.join([textwrap.fill(s, width) for s in value.split('\n\n')])


def indent(value, level=0):
    return ('\n' + ' ' * level).join(value.split('\n'))


def pad(value, min_width):
    tab_count = (min_width / TAB_WIDTH - len(value) / TAB_WIDTH) + 1
    return value + ('\t' * int(tab_count))


def split(value, delimiter):
    return value.split(delimiter)


def values(lst, key):
    """ Go through the list of dictionaries and add all the value_list of
    a certain key to a list.
    """
    value_list = []
    for item in lst:
        if isinstance(item, dict) and key in item:
            if item[key] not in value_list:
                value_list.append(item[key])
    return value_list


def listify(node):
    if isinstance(node, list) or isinstance(node, tuple):
        return node
    else:
        return [node]
