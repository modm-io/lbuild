#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
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
    def __init__(self, module, filename_in: str, filename_out: str, time=None):
        self.modulename = module.fullname
        self.modulepath = module.path

        self.filename_in = filename_in
        self.filename_out = filename_out

        self.time = time

    @property
    def filename_local_in(self):
        """
        Remove the module path from the output filename.
        """
        localfile = os.path.join(os.path.relpath(os.path.dirname(self.filename_in),
                                                 self.modulepath),
                                 os.path.basename(self.filename_in))
        return os.path.normpath(localfile)

    def __repr__(self):
        return "<{}: {} -> {}>".format(self.modulename, self.filename_in, self.filename_out)


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

    def log(self, module, filename_in: str, filename_out: str, time=None):
        operation = Operation(module, filename_in, filename_out, time)
        LOGGER.debug(str(operation))

        previous = self._build_files.get(filename_out, None)
        if previous is not None:
            raise BlobBuildException("Overwrite file '{}' from '{}' (module '{}'). Previously "
                                     "generated from '{}' (module '{}')."
                                     .format(filename_out,
                                             filename_in,
                                             module.fullname,
                                             previous.filename_in,
                                             previous.modulename))

        self._build_files[filename_out] = operation
        self.operations.append(operation)

        return operation

    def get_operations_per_module(self, modulename: str):
        """
        Get all operations which have been performed for the given module and
        its submodules.
        
        Keyword arguments:
        modulename -- Full module name.
        """
        module_operations = [operation for operation in self.operations if
                             operation.modulename.startswith(modulename)]
        return module_operations

    def to_xml(self, to_string=True):
        """
        Convert the complete build log into a XML representation.
        """
        rootnode = lxml.etree.Element("buildlog")

        for operation in self.operations:
            operationnode = lxml.etree.SubElement(rootnode, "operation")

            modulenode = lxml.etree.SubElement(operationnode, "module")
            modulenode.text = operation.modulename
            srcnode = lxml.etree.SubElement(operationnode, "source")
            srcnode.text = operation.filename_in
            destnode = lxml.etree.SubElement(operationnode, "destination")
            destnode.text = operation.filename_out

            if operation.time is not None:
                timenode = lxml.etree.SubElement(operationnode, "time")
                timenode.text = "{:.3f} ms".format(operation.time * 1000)

        if to_string:
            return lxml.etree.tostring(rootnode,
                                       encoding="UTF-8",
                                       pretty_print=True,
                                       xml_declaration=True,)
        else:
            return rootnode

