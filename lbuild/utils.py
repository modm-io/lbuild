#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, 2017-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import uuid
import shutil
import fnmatch
import importlib.util
import importlib.machinery

import lbuild.exception as le

DEFAULT_IGNORE_PATTERNS = [
    "*/.git*",
    "*/.DS_Store*",
    "*/__pycache__",
    "*/module.lb",
    "*/repo.lb",
    "*/*.pyc"
]


def ignore_files(*files):
    """
    Ignore file and folder names without checking the full path.

    Example: the following code with ignore all files with the ending `.lb`:
    ```
    env.copy(".", ignore=env.ignore_files("*.lb"))
    ```

    Based on the shutil.ignore_patterns() function.
    """
    return shutil.ignore_patterns(*files)


def ignore_patterns(*patterns):
    """
    Ignore patterns based on the absolute file path.

    Use an `*` at the beginning to match relative paths:
    ```
    env.copy(".", ignore=env.ignore_patterns("*platform/*.lb"))
    ```
    This ignores all files in the `platform` sub-directory with the
    ending `.lb`.
    """

    def check(path, files):
        ignored = set()
        for pattern in patterns:
            for filename in files:
                if fnmatch.fnmatch(os.path.join(path, filename), pattern):
                    # The copytree function uses only the filename to check
                    # which files should be ignored, not the absolute path.
                    ignored.add(filename)
        return ignored

    return check


def _listify(obj):
    if obj is None:
        return list()
    if isinstance(obj, (list, tuple, set, range)):
        return list(obj)
    if hasattr(obj, "__iter__") and not hasattr(obj, "__getitem__"):
        return list(obj)
    return [obj, ]


def listify(*objs):
    """
    Convert arguments to list if they are not already a list.
    """
    return [l for o in objs for l in _listify(o)]


def listrify(*objs):
    """
    Convert arguments to list of strings.
    """
    return list(map(str, listify(*objs)))


def get_global_functions(env, required, optional=None):
    """
    Get global functions an environment.

    Args:
        required: List of required functions.
        optional: List of optional functions.
    """

    def get(name, fail=True):
        if isinstance(env, dict):
            val = env.get(name, None)
        else:
            val = getattr(env, name, None)
        if fail and val is None:
            raise le.LbuildUtilsFunctionNotFoundException(name, required, optional)
        return val

    if optional is None:
        optional = []

    functions = {}
    for name in required + optional:
        function = get(name, name in required)
        if function is not None:
            functions[name] = function

    return functions


def load_module_from_file(filename, local, modulename=None):
    """
    Load a python module from a local file.

    Args:
        filename: Name of the file to load. The file extension is ignored.
        local: dictionary of symbols which will be added to the global
            namespace when executing the module code.
        modulename: Name of the module. When set to `None`.

    Returns:
        Namespace of the module.
    """
    # The actual name of the module is only known after it is loaded. Therefore
    # a UUID is used instead here.
    if modulename is None:
        modulename = "lbuild.modules.{}".format(uuid.uuid1())

    loader = importlib.machinery.SourceFileLoader(modulename, filename)

    spec = importlib.util.spec_from_loader(loader.name, loader)
    try:
        module = importlib.util.module_from_spec(spec)
    except AttributeError:
        import types
        module = types.ModuleType(modulename)

    # Prepare the environment of the module. Everything set here will
    # be available in the global namespace when executing the module.
    module.__dict__.update(local)

    try:
        # Load the module. This executes the code inside the lbuild module file.
        loader.exec_module(module)
    except Exception as error:
        raise le.LbuildForwardException(modulename, error)

    sys.modules[modulename] = module
    return module.__dict__


def with_forward_exception(module, function):
    """
    Run a function a store exceptions as forward exceptions.
    """
    try:
        return function()
    except le.LbuildException:
        raise
    except Exception as error:
        raise le.LbuildForwardException(module, error)


import errno
import tempfile

def is_pathname_valid(path):
    if not isinstance(path, str) or not path:
        return False
    if (os.path.sep + os.path.sep) in path:
        return False
    return _is_pathname_valid(path)

# See https://stackoverflow.com/a/34102855
def _is_pathname_valid(pathname: str) -> bool:
    try:
        _, pathname = os.path.splitdrive(pathname)
        with tempfile.TemporaryDirectory() as root_dirname:
            root_dirname = root_dirname.rstrip(os.path.sep) + os.path.sep
            for pathname_part in pathname.split(os.path.sep):
                try:
                    os.lstat(root_dirname + pathname_part)
                except OSError as exc:
                    if hasattr(exc, "winerror"):
                        if exc.winerror == 123:
                            return False
                    elif exc.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                        return False
    except TypeError as exc:
        return False
    return True
