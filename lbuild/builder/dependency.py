#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import re
import collections


def get_valid_identifier(name):
    return re.sub(r'\W|^(?=\d)', '_', name)


def graphviz(builder, selected_modules, depth, clustered=None):
    output = []
    output.append("digraph dependencies")
    output.append("{")
    output.append("\trankdir=BT;")

    selected_modules = builder.parser.find_modules(selected_modules)
    modules = builder.parser.resolve_dependencies(selected_modules, depth)

    # Check whether all available modules are selected for displaying
    all_selected = (len(builder.parser.all_modules(selected=False)) == len(modules))

    # Sort modules by repository
    repositories = collections.defaultdict(list)
    for module in modules:
        repositories[module.repository.name].append(module)

    if clustered is None:
        clustered = len(repositories) > 1

    for repo_name, rmodules in repositories.items():
        if clustered:
            output.append("\tsubgraph cluster{}".format(get_valid_identifier(repo_name)))
        else:
            output.append("\tsubgraph {}".format(get_valid_identifier(repo_name)))

        output.append("\t{")
        output.append("\t\tlabel = \"{}\";".format(repo_name))
        output.append("\t\tnode [style=filled, shape=box];")
        output.append("")
        for module in sorted(rmodules):
            if clustered:
                # Remove the repository name for the clusted output. The
                # repository name is mentioned in the cluster already.
                name = ":\\n".join(module.fullname.split(":")[1:])
            else:
                name = ":\\n".join(module.fullname.split(":"))

            attributes = []
            attributes.append("label=\"{}\"".format(name))

            if not all_selected:
                if module in selected_modules:
                    attributes.append('style="filled,bold"')
                else:
                    for dep in sorted(module.dependencies):
                        if dep not in modules:
                            attributes.append('style="filled,dashed"')
                            break
                    else:
                        attributes.append('style="filled,solid"')

            output.append("\t\t{} [{}];".format(get_valid_identifier(module.fullname),
                                                ", ".join(attributes)))
        output.append("\t}")

    for module in sorted(modules):
        for dep in sorted(module.dependencies):
            if not all_selected:
                if dep not in modules:
                    # Dependencies may not be drawn if the depth of the
                    # dependency resolution is too small.
                    continue

            output.append("\t{} -> {};".format(get_valid_identifier(module.fullname),
                                               get_valid_identifier(dep.fullname)))

    output.append("}")
    return "\n".join(output)
