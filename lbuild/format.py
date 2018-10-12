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
import re
import sys
import shutil
import colorful

import lbuild.node
import lbuild.filter

plain = not sys.stdout.isatty()
WIDTH = shutil.get_terminal_size((100, 0)).columns

color_scheme = {
    "parser": None,
    "repository": None, #colorful.deepSkyBlue,
    "option": None, #colorful.lightSteelBlue,
    "module": None,
    "description": None,
    "short_description": None,
    "error": colorful.red,
}

def ansi_escape(obj=None):
    if plain:
        return ""
    name = obj
    if isinstance(obj, lbuild.node.BaseNode):
        name = obj.type.name.lower()
    col = color_scheme.get(name, "nope")
    if col == "nope":
        try:
            col = getattr(colorful, name)
        except:
            col = None
    return str(col) if col is not None else ""


class color_str:
    def __init__(self, string=None):
        self._string = ""
        self._content = []
        if isinstance(string, color_str):
            self._string = string._string
            self._content = string._content.copy()
        elif string is not None:
            self._string = string
            self._content = [("", self._string)]

    def wrap(self, name):
        style = ansi_escape(name)
        if style is not None:
            if name in ["underlined", "bold"]:
                if name == "underlined": name = "underline";
                close = ansi_escape("no_" + name)
            else:
                close = ansi_escape("close_fg_color")
            self._content = \
                [(style, "")] + \
                self._content + \
                [(close, "")]
        return self

    def join(self, strings):
        result = color_str()
        for ii, v in enumerate(strings):
            result += color_str(v)
            if ii < len(strings) - 1:
                result += self
        return result

    def limit(self, offset=0):
        if len(self) <= (WIDTH - offset):
            return str(self)

        mark = " ..."
        width = WIDTH - offset - len(mark)
        if width < 0: width = 0
        style_str = ""
        raw_string = ""
        for style, content in self._content:
            style_str += style;
            if len(raw_string + content) >= width:
                style_str += content[:width - len(raw_string)]
                return style_str + ansi_escape("reset") + mark
            raw_string += content
            style_str += content
        return style_str

    def __add__(self, other):
        color = color_str()
        if isinstance(other, color_str):
            color._content = self._content + other._content
            color._string = self._string + other._string
        else:
            color._string = other
            color._content = self._content
        return color

    def __len__(self):
        return len(self._string)

    def __iter__(self):
        return iter(self._string)

    def __contains__(self, string):
        return (string in self._string)

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


c = color_str


def format_option_name(node, fullname=True):
    line = c(node.fullname if fullname else node.name).wrap(node).wrap("bold")
    if not node.is_default():
        line.wrap("underlined")
    return line


def format_option_value(node, single_line=True):
    offset = -1
    if node.value is None:
        return (c("REQUIRED").wrap("error").wrap("bold"), offset, False)
    value = node.format_value()
    if single_line:
        value = value.replace("\n", " ")
    return (c(value).wrap("bold"), offset, True)


def format_option_values(node, offset=0, single_line=True):
    values = c(node.format_values())
    if not single_line:
        if WIDTH - offset > 10:
            values = lbuild.filter.indent(lbuild.filter.wordwrap(values._string, WIDTH - offset), offset)
    return c(values).wrap("bold")


def format_option_value_description(node, offset=0, single_line=None):
    value = format_option_value(node, bool(single_line))
    offset = offset + len(value[0]) if value[1] < 0 else value[1]
    single_line = value[2] if single_line is None else single_line
    values = format_option_values(node, offset + 5, single_line)
    return value[0] + c(" in [") + values +  c("]")


def format_option_short_description(node):
    line = format_option_name(node) + c(" = ")
    line += format_option_value_description(node, offset=len(line))
    if "REQUIRED" not in line:
        line = line.limit()
    return str(line)


def format_description(node, description):
    output = [c(">> ") + c(node.fullname).wrap(node).wrap("bold"), c("")]
    if len(description):
        output += [c(description.strip(" \n"))]

    if node.type == node.Type.OPTION:
        value = format_option_value(node, single_line=False)[0]
        values = format_option_values(node, offset=9, single_line=False)
        output += [c(""), c("Value: ") + value, c("Inputs: [") + values + c("]")]

    for option in node.options:
        output.extend([c("\n"), c(">>") + c(option.description)])
    return "\n".join(map(str, output))


def format_short_description(node, description):
    lines = description.strip(" \n").splitlines() + [""]
    return lines[0].strip()


def format_node(node, prefix):
    context = c(node.fullname)
    if node._type == node.Type.REPOSITORY:
        context = c(node.name + " @ " + os.path.relpath(node._filepath, os.getcwd()))
    elif node._type == node.Type.OPTION:
        context = format_option_name(node, fullname=False)

    descr = (c(node.__class__.__name__ + "(") + context + c(")")).wrap(node)

    offset = node.depth*4
    if node._type == node.Type.OPTION:
        descr += c(" = ")
        descr += format_option_value_description(node, offset=offset+len(descr), single_line=True)
    else:
        descr += c("   " + node.short_description)

    return descr.limit(offset)
