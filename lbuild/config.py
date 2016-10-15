#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import pkgutil
import logging
import collections
import lxml.etree

from .exception import BlobException

LOGGER = logging.getLogger('lbuild.config')
DEFAULT_CACHE_FOLDER = ".lbuild_cache"

def load_and_verify(configfile):
    """
    Verify the XML structure.
    """
    try:
        LOGGER.debug("Parse configuration '%s'", configfile)
        xmlroot = lxml.etree.parse(configfile)

        xmlschema = lxml.etree.fromstring(pkgutil.get_data('lbuild', 'resources/configuration.xsd'))

        schema = lxml.etree.XMLSchema(xmlschema)
        schema.assertValid(xmlroot)

        xmltree = xmlroot.getroot()
    except OSError as error:
            raise BlobException(error)
    except (lxml.etree.DocumentInvalid,
            lxml.etree.XMLSyntaxError,
            lxml.etree.XMLSchemaParseError,
            lxml.etree.XIncludeError) as error:
        raise BlobException("While parsing '{}':"
                            " {}".format(error.error_log.last_error.filename,
                                         error))

    projectpath = os.path.dirname(configfile)
    return xmltree, projectpath

def get_cachefolder(xmltree, projectpath):
    cache_node = xmltree.find("repositories/cache")
    if cache_node is not None:
        cachefolder = cache_node.text
        if not os.path.isabs(cachefolder):
            cachefolder = os.path.join(projectpath, cachefolder)
    else:
        cachefolder = os.path.join(projectpath, DEFAULT_CACHE_FOLDER)

    return cachefolder

def to_dict(xmltree):
    """
    Convert XML to a Python dictionary according to
    http://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html
    """
    d = {xmltree.tag: {} if xmltree.attrib else None}
    children = []
    for c in xmltree:
        children.append(c)
    if children:
        dd = collections.defaultdict(list)
        for dc in map(to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {xmltree.tag: {k:v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if xmltree.attrib:
        d[xmltree.tag].update(('@' + k, v) for k, v in xmltree.attrib.items())
    if xmltree.text:
        text = xmltree.text.strip()
        if children or xmltree.attrib:
            if text:
                d[xmltree.tag]['#text'] = text
        else:
            d[xmltree.tag] = text
    return d
