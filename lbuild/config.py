#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import anytree
import pkgutil
import logging
import collections
import lxml.etree
from os.path import realpath, join
from pathlib import Path

from .exception import LbuildException

import lbuild.module

LOGGER = logging.getLogger('lbuild.config')
DEFAULT_CACHE_FOLDER = ".lbuild_cache"

class ConfigNode(anytree.AnyNode):
    def __init__(self, parent=None):
        anytree.AnyNode.__init__(self, parent, filename=Path())
        self._cachefolder = Path()
        self._extends = collections.defaultdict(list)
        self._vcs = []
        self._repositories = []
        self._modules = []
        self._options = {}

    @property
    def repositories(self):
        return self._repositories

    @property
    def modules(self):
        return self._modules

    @property
    def options(self):
        return self._options

    @property
    def vcs(self):
        return self._vcs

    @property
    def cachefolder(self):
        return self._cachefolder

    def add_commandline_options(self, cmd_options):
        for option in cmd_options:
            parts = option.split('=')
            self._options[parts[0]] = parts[1]

    def _flatten(self, config):
        for node in (list(self.siblings) + [self]):
            config._cachefolder = node._cachefolder
            config._extends.update(node._extends)
            config._vcs.extend(node._vcs)
            config._repositories.extend(node._repositories)
            config._modules.extend(node._modules)
            config._options.update(node._options)
        if self.parent:
            self.parent._flatten(config)

    def flatten(self):
        config = ConfigNode()
        self.last._flatten(config)
        config._repositories = list(set(config._repositories))
        config._modules = list(set(config._modules))
        return config

    def extend(self, node, config):
        if config and node:
            below = node.children[0] if len(node.children) else None
            config.parent = node
            if below:
                below.parent = config

    def extend_last(self, config):
        self.extend(self.last, config)

    @property
    def last(self):
        descendants = self.root.descendants
        return descendants[-1] if len(descendants) else self

    def find(self, filename):
        return anytree.find_by_attr(self.root, name="filename", value=filename)

    def render(self):
        if self.filename == Path():
            return "ConfigNode(Empty)"
        return anytree.RenderTree(self, anytree.ContRoundStyle())

    @staticmethod
    def from_filesystem(startpath=None, name="lbuild.xml"):
        startpath = Path(startpath) if startpath else Path.cwd()
        while startpath.exists():
            config = (startpath / name)
            if config.exists():
                return ConfigNode.from_file(config)
            if startpath.parent == startpath:
                break
            startpath = startpath.parent
        return None

    @staticmethod
    def from_file(configfile, parent=None, fail_silent=False):
        filename = os.path.relpath(str(configfile), os.getcwd())
        LOGGER.debug("Parse configuration '{}'".format(filename))
        if fail_silent and not os.path.exists(filename):
            return None

        xmltree = ConfigNode._load_and_verify(configfile)

        config = ConfigNode(parent)
        config.filename = filename
        configpath = str(Path(config.filename).parent)
        # load extend strings
        for e in xmltree.iterfind("extends"):
            cpath = Path(ConfigNode._rel_path(e.text, configpath))
            if cpath.exists():
                ConfigNode.from_file(str(cpath), config)
            else:
                config._extends[config.filename].append(e.text)

        # Load cachefolder
        cache_node = xmltree.find("repositories/cache")
        if cache_node is not None:
            config._cachefolder = ConfigNode._rel_path(cache_node.text, configpath)
        else:
            config._cachefolder = join(configpath, DEFAULT_CACHE_FOLDER)

        # Load version control nodes
        for vcs_node in xmltree.iterfind("repositories/repository/vcs"):
            config._vcs += [ConfigNode.to_dict(vcs) for vcs in vcs_node.iterchildren()]

        # Load repositories
        for path_node in xmltree.iterfind("repositories/repository/path"):
            repopath = path_node.text.format(cache=config._cachefolder)
            filename = realpath(join(configpath, repopath))
            config._repositories.append(filename)

        # Load all requested modules
        config._modules = xmltree.xpath('modules/module/text()')

        # Load options
        for option_node in xmltree.xpath('options/option'):
            name = option_node.attrib['name']
            value = option_node.attrib.get('value', option_node.text)
            config._options[name] = value

        return config

    @staticmethod
    def _load_and_verify(configfile):
        try:
            xmlroot = lxml.etree.parse(str(configfile))

            xmlschema = lxml.etree.fromstring(pkgutil.get_data('lbuild', 'resources/configuration.xsd'))
            schema = lxml.etree.XMLSchema(xmlschema)
            schema.assertValid(xmlroot)

            xmltree = xmlroot.getroot()
        except OSError as error:
            raise LbuildException(error)
        except (lxml.etree.DocumentInvalid,
                lxml.etree.XMLSyntaxError,
                lxml.etree.XMLSchemaParseError,
                lxml.etree.XIncludeError) as error:
            raise LbuildException("While parsing '{}': {}".format(
                                  error.error_log.last_error.filename, error))
        return xmltree

    @staticmethod
    def _rel_path(path, configpath):
        if os.path.isabs(path):
            return path
        else:
            return join(configpath, path)

    @staticmethod
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
            for dc in [ConfigNode.to_dict(c) for c in  children]:
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

