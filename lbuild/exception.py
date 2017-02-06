#!/usr/bin/env python3
#
# Copyright (c) 2015-2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.


class BlobException(Exception):
    """
    Base class for exception thrown by lbuild.
    """
    pass


class BlobArgumentException(BlobException):
    """
    Raised if something is wrong with the command line arguments.
    """
    pass


class BlobOptionFormatException(BlobException):
    """
    Exception for all invalid option names.
    """
    def __init__(self, name):
        BlobException.__init__(self,
                               "Invalid option format for '{}'. Option must "
                               "options are one (repository option) or "
                               "two and more (module option) colons.".format(name))


class BlobAttributeException(BlobException):
    def __init__(self, name):
        BlobException.__init__(self,
                               ("The attribute {} may only be changed in "
                                "the init(...) method".format(name)))

class BlobTemplateException(BlobException):
    """
    Error in Jinja2 template evaluation.
    """
    pass

class BlobBuildException(BlobException):
    """
    Exceptions raised during the build of project.

    E.g. when a previously generated file is being overwritten by another
    module.
    """
    pass

