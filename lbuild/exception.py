#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.


class LbuildException(Exception):
    """
    Base class for exception thrown by lbuild.
    """
    pass


class LbuildArgumentException(LbuildException):
    """
    Raised if something is wrong with the command line arguments.
    """
    pass


class LbuildOptionFormatException(LbuildException):
    """
    Exception for all invalid option names.
    """

    def __init__(self, name):
        LbuildException.__init__(self,
                                 "Invalid option format for '{}'. Option must "
                                 "options are one (repository option) or "
                                 "two and more (module option) colons.".format(name))


class LbuildAttributeException(LbuildException):

    def __init__(self, name):
        LbuildException.__init__(self,
                                 "The attribute '{}' may only be changed in "
                                 "the init(...) method".format(name))


class LbuildTemplateException(LbuildException):
    """
    Error in Jinja2 template evaluation.
    """
    pass


class LbuildValidateException(LbuildException):
    pass


class LbuildBuildException(LbuildException):
    """
    Exceptions raised during the build of project.

    E.g. when a previously generated file is being overwritten by another
    module.
    """
    pass


class LbuildAggregateException(LbuildException):
    """
    Collection of multiple exceptions.
    """

    def __init__(self, exceptions):
        LbuildException.__init__(self, "Multiple Exceptions")

        self.exceptions = exceptions


class LbuildForwardException(LbuildException):
    """
    Handler for regular Python exception thrown in user defined functions.

    Use to forward the exception to the command line interface and provide
    additional informations.
    """

    def __init__(self, module, exception):
        LbuildException.__init__(self, "Forward Exceptions")

        self.module = module
        self.exception = exception
