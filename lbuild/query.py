#!/usr/bin/env python3
#
# Copyright (c) 2019, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import inspect
import textwrap

from .exception import LbuildQueryConstructionException
from .node import BaseNode


class Query(BaseNode):

    def __init__(self, function, name=None):
        BaseNode.__init__(self, name, BaseNode.Type.QUERY)
        if not callable(function):
            raise LbuildQueryConstructionException(self, "'{}' must be callable!".format(function))
        fname = function.__name__
        if name is None:
            if "<lambda>" in fname:
                raise LbuildQueryConstructionException(self, "'{}' must have a name!".format(function))
            self.name = fname

        self._description = str(inspect.getdoc(function))
        self.suffix = str(inspect.signature(function))
        self._function = function

    @property
    def module(self):
        return self.parent

    @property
    def description_name(self):
        return self.fullname + self.suffix

    def value(self, env):
        return self._function


class EnvironmentQuery(Query):

    def __init__(self, factory, name=None):
        Query.__init__(self, name=name, function=factory)
        if len(inspect.signature(factory).parameters.keys()) != 1:
            raise LbuildQueryConstructionException(self, "'{}' must take 'env' as argument!".format(factory))
        self.suffix = ""
        self.__result = None
        self.__called = False

    def value(self, env):
        if not self.__called:
            self.__result = self._function(env)
            self.__called = True
        return self.__result
