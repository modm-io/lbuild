#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import re

import lbuild.parser

def get_valid_identifier(name):
    return re.sub('\W|^(?=\d)', '_', name)

def graphviz(repositories, clustered=False):
    output = []
    output.append("digraph dependencies {")
    # output.append("rankdir=LR;")

    modules = {}
    for repository in repositories.values():
        for module in repository.modules.values():
            modules[module.name] = module

    for name, repository in repositories.items():
        if clustered:
            output.append("subgraph cluster{} {{".format(get_valid_identifier(name)))
        else:
            output.append("subgraph {} {{".format(get_valid_identifier(name)))
        output.append("label = \"{}\";".format(name))
        output.append("node [style=filled, shape=box];")
        for module in repository.modules.values():
            if clustered:
                # Remove the repository name
                name = ":\\n".join(module.fullname.split(":")[1:])
            else:
                name = ":\\n".join(module.fullname.split(":"))
            output.append("{} [label=\"{}\"];".format(get_valid_identifier(module.fullname), name))

        output.append("}")

    for module in modules.values():
        for dep in module.dependencies:
            dep = lbuild.parser.Parser.find_module(modules, dep)
            output.append("{} -> {};".format(get_valid_identifier(module.fullname),
                                             get_valid_identifier(dep.fullname)))

    output.append("}")
    return "\n".join(output)
