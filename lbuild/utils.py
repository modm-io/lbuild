#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import sys
import uuid
import importlib.util
import importlib.machinery

def listify(node):
    return [node, ] if (not isinstance(node, list)) else node

def load_module_from_file(filename, local, modulename=None):
    """
    Load a python module from a local file.

    Keyword arguments:
    filename -- Name of the file to load. The file extension is ignored.
    local -- dictionary of symbols which will be added to the global
        namespace when executing the module code.
    modulename -- Name of the module. When set to `None`

    Returns:
        Namespace of the module.
    """
    # The actual name of the module is only known after it is loaded. Therefore
    # a UUID is used instead here.
    if modulename is None:
        modulename = "lbuild.modules.{}".format(uuid.uuid1())
    loader = importlib.machinery.SourceFileLoader(modulename, filename)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)

    # Prepare the environment of the module. Everything set here will
    # be available in the global namespace when executing the module.
    module.__dict__.update(local)

    # Load the module. This executes the code inside the lbuild module file.
    loader.exec_module(module)

    sys.modules[modulename] = module
    return module.__dict__
