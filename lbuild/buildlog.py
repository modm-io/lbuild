#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import logging
import lxml.etree
from .exception import BlobBuildException

LOGGER = logging.getLogger('lbuild.buildlog')


class Operation:
    """
    Representation of a build operation.

    Stores the connection between a generated file and its template and module
    from within it was generated.
    """
    def __init__(self, module, filename_in: str, filename_out: str):
        self.module = module.fullname
        self.modulepath = module.path

        self.filename_in = filename_in
        self.filename_out = filename_out

    def __str__(self):
        return "{} -> {}".format(self.filename_in, self.filename_out)


class BuildLog:
    """
    Log of a all files being generated during the build step.

    Used to detect if a previously generated file is being overwritten by
    another module. Also allow to later find out which module has generated
    a specific file.
    """
    def __init__(self):
        self.operations = []
        self._build_files = {}

    def log(self, module, filename_in: str, filename_out: str):
        operation = Operation(module, filename_in, filename_out)
        LOGGER.debug(str(operation))

        previous = self._build_files.get(filename_out, None)
        if previous is not None:
            raise BlobBuildException("Overwrite file '{}' from '{}' (module '{}'). Previously "
                                     "generated from '{}' (module '{}')."
                                     .format(filename_out,
                                             filename_in,
                                             module.fullname,
                                             previous.filename_in,
                                             previous.module))

        self._build_files[filename_out] = operation
        self.operations.append(operation)

    def to_xml(self, to_string=True):
        rootnode = lxml.etree.Element("buildlog")

        for operation in self.operations:
            operationnode = lxml.etree.SubElement(rootnode, "operation")

            modulenode = lxml.etree.SubElement(operationnode, "module")
            modulenode.text = operation.module
            srcnode = lxml.etree.SubElement(operationnode, "source")
            srcnode.text = operation.filename_in
            destnode = lxml.etree.SubElement(operationnode, "destination")
            destnode.text = operation.filename_out

        if to_string:
            return lxml.etree.tostring(rootnode,
                                       encoding="UTF-8",
                                       pretty_print=True,
                                       xml_declaration=True,)
        else:
            return rootnode
