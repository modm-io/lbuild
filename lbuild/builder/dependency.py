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
    return re.sub(r'\W|^(?=\d)', '_', name)

def graphviz(repositories, clustered=False):
    output = []
    output.append("digraph dependencies")
    output.append("{")
    # output.append("\trankdir=LR;")

    modules = {}
    for repository in repositories.values():
        for module in repository.modules.values():
            modules[module.name] = module

    for name, repository in repositories.items():
        if clustered:
            output.append("\tsubgraph cluster{}".format(get_valid_identifier(name)))
        else:
            output.append("\tsubgraph {}".format(get_valid_identifier(name)))
        output.append("\t{")
        output.append("\t\tlabel = \"{}\";".format(name))
        output.append("\t\tnode [style=filled, shape=box];")
        output.append("")
        for module in sorted(repository.modules.values()):
            if clustered:
                # Remove the repository name for the clusted output. The
                # repository name is meantioned in the cluster already.
                name = ":\\n".join(module.fullname.split(":")[1:])
            else:
                name = ":\\n".join(module.fullname.split(":"))
            output.append("\t\t{} [label=\"{}\"];".format(get_valid_identifier(module.fullname), name))

        output.append("\t}")

    for module in sorted(modules.values()):
        for dep in sorted(module.dependencies):
            dep = lbuild.parser.Parser.find_module(modules, dep)
            output.append("\t{} -> {};".format(get_valid_identifier(module.fullname),
                                               get_valid_identifier(dep.fullname)))

    output.append("}")
    return "\n".join(output)
