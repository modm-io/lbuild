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
from .exception import BlobException

LOGGER = logging.getLogger('lbuild.buildlog')


class Operation:

    def __init__(self, module, filename_in: str, filename_out: str):
        self.module = module.fullname
        self.modulepath = module.path

        self.filename_in = filename_in
        self.filename_out = filename_out


class BuildLog:

    def __init__(self):
        self.operations = {}
    
    def log(self, module, filename_in: str, filename_out: str):

        operation = Operation(module, filename_in, filename_out)

        previous = self.operations.get(filename_out, None)
        if previous is not None:
            raise BlobException("Overwrite file '{}' with template '{}'. Previously "
                                "generated from template '{}'.".format(filename_out,
                                                                       filename_in,
                                                                       previous.filename_in))

        self.operations[filename_out] = operation
