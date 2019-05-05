#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import shutil
import anytree
import colorful

import lbuild.node
import lbuild.filter

PLAIN = False
WIDTH = shutil.get_terminal_size((100, 0)).columns
SHOW_NODES = {
    lbuild.node.BaseNode.Type.REPOSITORY,
    lbuild.node.BaseNode.Type.MODULE,
    lbuild.node.BaseNode.Type.OPTION,
    lbuild.node.BaseNode.Type.CONFIG,
}

COLOR_SCHEME = {
    "parser": None,
    "repository": None,
    "option": None,
    "query": None,
    "config": None,
    "collector": None,
    "module": None,
    "description": None,
    "short_description": None,
    "error": colorful.red,  # pylint: disable=no-member
}


def ansi_escape(obj=None):
    if PLAIN:
        # The terminal does not support color
        return ""

    name = obj
    if isinstance(obj, lbuild.node.BaseNode):
        name = obj.type.name.lower()

    col = COLOR_SCHEME.get(name, "nope")
    if col == "nope":
        try:
            col = getattr(colorful, name)
        except AttributeError:
            col = None

    return str(col) if col is not None else ""


class ColorWrapper:

    def __init__(self, string=None):
        self._string = ""
        self._content = []

        if isinstance(string, ColorWrapper):
            self._string = string._string
            self._content = string._content.copy()
        elif string is not None:
            self._string = string
            self._content = [("", self._string)]

    def wrap(self, name):
        style = ansi_escape(name)
        if style is not None:
            if name in ["underlined", "bold"]:
                close = ansi_escape("no_" + name)
            else:
                close = ansi_escape("close_fg_color")
            self._content = [(style, "")] + self._content + [(close, "")]
        return self

    def join(self, strings):
        result = ColorWrapper()
        for index, string in enumerate(strings):
            result += ColorWrapper(string)
            if index < len(strings) - 1:
                result += self
        return result

    def limit(self, offset=0):
        if len(self) <= (WIDTH - offset):
            return str(self)

        mark = " ..."
        width = WIDTH - offset - len(mark)
        if width < 0:
            width = 0
        style_str = ""
        raw_string = ""
        for style, content in self._content:
            style_str += style
            if len(raw_string + content) >= width:
                style_str += content[:width - len(raw_string)]
                return style_str + ansi_escape("reset") + mark
            raw_string += content
            style_str += content
        return style_str

    def __add__(self, other):
        color = ColorWrapper()
        if isinstance(other, ColorWrapper):
            color._content = self._content + other._content
            color._string = self._string + other._string
        else:
            color._content = self._content
            color._string = other
        return color

    def __len__(self):
        return len(self._string)

    def __iter__(self):
        return iter(self._string)

    def __contains__(self, string):
        return string in self._string

    def __getattr__(self, name):
        color = ansi_escape(name)
        if color is not None:
            self._content += [(color, "")]
        return self

    def __eq__(self, other):
        return self._string == other._string

    def __ne__(self, other):
        return self._string != other._string

    def __str__(self):
        string = ""
        for style, content in self._content:
            string += style + content
        return string + ansi_escape("reset")


_cw = ColorWrapper


def format_option_name(node, fullname=True):
    line = _cw(node.fullname if fullname else node.name).wrap(node).wrap("bold")
    if not node.is_default():
        line.wrap("underlined")
    return line


def format_option_value(node, single_line=True):
    offset = -1
    if node.value is None:
        return (_cw("REQUIRED").wrap("error").wrap("bold"), offset, False)
    value = node.format_value()
    if single_line:
        value = value.replace("\n", " ")
    return (_cw(value).wrap("bold"), offset, True)


def format_option_values(node, offset=0, single_line=True):
    values = node.format_values()
    if not single_line:
        if (offset + len(values)) > WIDTH:
            values = lbuild.filter.indent(lbuild.filter.wordwrap(values._string, WIDTH - offset),
                                          offset)
    return _cw(values).wrap("bold")


def format_option_value_description(node, offset=0, single_line=None):
    value = format_option_value(node, bool(single_line))
    offset = offset + len(value[0]) if value[1] < 0 else value[1]
    single_line = value[2] if single_line is None else single_line
    values = format_option_values(node, offset + 5, single_line)
    return value[0] + _cw(" in [") + values + _cw("]")


def format_option_short_description(node):
    line = format_option_name(node) + _cw(" = ")
    line += format_option_value_description(node, offset=len(line))
    if "REQUIRED" not in line:
        line = line.limit()
    return str(line)


def format_description(node, description):
    type_description = "  [{}]".format(node.class_name)
    output = [_cw(">> ") + _cw(node.description_name).wrap(node).wrap("bold") + _cw(type_description)]
    if description:
        description = description.strip()
        if len(description):
            output += [_cw(""), _cw(description)]

    if node.type == node.Type.OPTION:
        value = format_option_value(node, single_line=False)[0]
        values = format_option_values(node, offset=9, single_line=False)
        output += [_cw(""), _cw("Value: ") + value, _cw("Inputs: [") + values + _cw("]")]
    elif node.type == node.Type.COLLECTOR:
        values = format_option_values(node, offset=9, single_line=False)
        output += [_cw(""), _cw("Inputs: [") + values + _cw("]")]

    children = []
    # Print every node except the submodule, due to obvious recursion
    for ntype in (SHOW_NODES - {lbuild.node.BaseNode.Type.MODULE}):
        children += node._findall(ntype, depth=2)

    for child in sorted(children, key=lambda c: (c.type, c.name)):
        output.extend([_cw("\n"), _cw(">>") + _cw(child.description)])

    return "\n".join(map(str, output))


def format_short_description(_, description):
    lines = description.strip().splitlines() + [""]
    return lines[0].strip().rstrip(".,:;!?")


def format_node(node, _, depth):
    name = _cw(node.name)
    class_name = _cw(node.class_name)
    if node._type == node.Type.REPOSITORY:
        name = _cw(node.name + " @ " + os.path.relpath(node._filepath, os.getcwd()))
    elif node._type == node.Type.OPTION:
        name = format_option_name(node, fullname=False)
    elif node._type in [node.Type.MODULE, node.Type.CONFIG]:
        name = _cw(node.fullname).wrap(node)
    elif node._type in [node.Type.QUERY, node.Type.COLLECTOR]:
        class_name = class_name.wrap("underlined")
        name = name.wrap("bold")

    descr = (class_name + _cw("(") + name + _cw(")")).wrap(node)

    offset = (node.depth - depth) * 4
    if node._type == node.Type.OPTION:
        descr += _cw(" = ")
        descr += format_option_value_description(node, offset=offset + len(descr), single_line=True)
    elif node._type == node.Type.COLLECTOR:
        descr += _cw(" in [")
        descr += format_option_values(node, offset=offset + len(descr), single_line=True)
        descr += _cw("]")

    descr += _cw("   " + node.short_description)

    return descr.limit(offset)


def format_node_tree(node, filterfunc=None):
    if filterfunc is None:
        filterfunc = lambda n: n.type in SHOW_NODES

    def childiter(nodes):
        nodes = [n for n in nodes if filterfunc(n)]
        return sorted(nodes, key=lambda node: (node._type, node.name))

    depth = node.depth
    render = anytree.RenderTree(node, childiter=childiter,
                                style=anytree.ContRoundStyle())
    lines = []
    for pre, _, node in render:
        lines.append(pre + format_node(node, pre, depth))
    return "\n".join(lines)
