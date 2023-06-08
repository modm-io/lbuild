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
from os.path import realpath, join
import glob
import re
import pkgutil
import logging
import collections
from pathlib import Path

import lxml.etree
import anytree

from .exception import LbuildConfigException, LbuildConfigNotFoundException, \
                       LbuildConfigSubstitutionException

LOGGER = logging.getLogger('lbuild.config')
DEFAULT_CACHE_FOLDER = ".lbuild_cache"


class ConfigNode(anytree.AnyNode):

    def __init__(self, parent=None):
        anytree.AnyNode.__init__(self, parent)

        self._outpath = None
        self._cachefolder = None
        self._extends = collections.defaultdict(list)
        self._vcs = []
        self._repositories = []
        self._modules = []
        self._options = {}
        self._collectors = []

        self.filename = Path()

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
    def collectors(self):
        return self._collectors

    @property
    def vcs(self):
        return self._vcs

    @property
    def outpath(self):
        return self._outpath

    @property
    def cachefolder(self):
        if self._cachefolder is None:
            return str(Path(self.filename).parent / DEFAULT_CACHE_FOLDER)
        return self._cachefolder

    def add_commandline_options(self, cmd_options):
        for option in cmd_options:
            parts = option.split('=')
            self._options[parts[0]] = (parts[1], os.path.join(os.getcwd(), "command-line"))

    def add_commandline_collectors(self, cmd_collectors):
        for collector in cmd_collectors:
            parts = collector.split('=')
            self._collectors.append( (parts[0], parts[1], os.path.join(os.getcwd(), "command-line")) )

    def _flatten(self, config):
        for node in list(self.siblings) + [self]:
            if node._cachefolder is not None:
                config._cachefolder = node._cachefolder
            if node._outpath is not None:
                config._outpath = node._outpath
            config._extends.update(node._extends)
            config._vcs.extend(node._vcs)
            config._repositories.extend(node._repositories)
            config._modules.extend(node._modules)
            config._options.update(node._options)
            config._collectors.extend(node._collectors)

        if self.parent:
            self.parent._flatten(config)

    def flatten(self):
        config = ConfigNode()
        config.filename = self.root.filename
        self.last._flatten(config)
        config._repositories = list(set(config._repositories))
        config._modules = list(set(config._modules))
        return config

    @staticmethod
    def extend(node, config):
        if config and node:
            below = next(iter(node.children), None)
            config.parent = node
            if below is not None:
                below.parent = config
        return node

    def extend_last(self, config):
        return self.extend(self.last, config)

    @property
    def last(self):
        descendants = self.root.descendants
        return descendants[-1] if descendants else self

    def find(self, filename):
        return anytree.find_by_attr(self.root, name="filename", value=filename)

    def render(self):
        if self.filename == Path():
            return "ConfigNode(command-line)"
        return anytree.RenderTree(self, anytree.ContRoundStyle())

    @staticmethod
    def from_path(startpath=None, name="lbuild.xml"):
        """
        Iterate upwards from the starting folder to find all
        configuration files.

        Args:
            startpath -- Start point for the iteration. If omitted
                the current working directory is used.
            name -- Filename of the configuation file.

        Returns:
            `ConfigNode` if a configuration file was found, `None`
            otherwise.
        """
        configs = []
        startpath = Path(os.path.abspath(startpath)) if startpath else Path.cwd()
        while startpath.exists():
            config = (startpath / name)
            if config.exists():
                configs.append(ConfigNode.from_file(config))
            if startpath.parent == startpath:
                break
            startpath = startpath.parent

        if not configs:
            return None
        if len(configs) == 1:
            return configs[0]

        first = configs[0]
        for node in configs[1:]:
            first.extend_last(node)
        return first

    @staticmethod
    def from_file(configfile, parent=None):
        """
        Load configuration from an XML configuration file.

        Args:
            configfile -- Path to the configuration file.
            parent -- Exisiting configuration which will be updated.

        Returns:
            Configuration as a `ConfigNode` instance.
        """
        filename = realpath(str(configfile))
        if not os.path.exists(filename):
            raise LbuildConfigNotFoundException(filename)

        xmltree = ConfigNode._load_and_verify(configfile)
        xmltree = ConfigNode._substitute_env(configfile, xmltree, env=os.environ)

        config = ConfigNode(parent)
        config.filename = os.path.relpath(filename)
        LOGGER.debug("Parse configuration '%s'", config.filename)
        configpath = os.path.dirname(config.filename)
        # load extend strings
        for node in xmltree.iterfind("extends"):
            cpath = Path(ConfigNode._rel_path(node.text, configpath))
            # We first need to check for the path, because in Windows `:`
            # is allowed to be part of the path (`C:\path`)
            try:
                cpath_exists = cpath.exists()
            except:
                cpath_exists = False
            if cpath_exists:
                ConfigNode.from_file(str(cpath), config)
            elif ":" in node.text:
                config._extends[config.filename].append(node.text)
            else:
                raise LbuildConfigNotFoundException(cpath, filename)


        # Load cachefolder
        cache_node = xmltree.find("repositories/cache")
        if cache_node is not None:
            config._cachefolder = ConfigNode._rel_path(cache_node.text, configpath)

        # Load version control nodes
        for vcs_node in xmltree.iterfind("repositories/repository/vcs"):
            config._vcs += [ConfigNode.to_dict(vcs) for vcs in vcs_node.iterchildren()]

        # Load repositories
        for path_node in xmltree.iterfind("repositories/repository/path"):
            repopath = path_node.text.format(cache=config._cachefolder)
            rfilename = ConfigNode._rel_path(repopath, configpath)
            config._repositories.append(rfilename)

        # Load glob repositories (optional)
        for glob_node in xmltree.iterfind("repositories/glob"):
            globPath = glob_node.text.format(cache=config._cachefolder)
            for f in glob.glob(globPath, recursive=True):
                rfilename = ConfigNode._rel_path(f, configpath)
                config._repositories.append(rfilename)

        # Load all requested modules
        config._modules = xmltree.xpath('modules/module/text()')

        # Load output path for lbuild and modules
        outpath = xmltree.find("outpath")
        if outpath is not None:
            config._outpath = ConfigNode._rel_path(outpath.text, configpath)

        # Load options
        for option_node in xmltree.xpath('options/option'):
            name = option_node.attrib['name']
            value = option_node.attrib.get('value', option_node.text)
            value = "" if value is None else value
            config._options[name] = (value, filename)

        # Load collectors
        for collector_node in xmltree.xpath('collectors/collect'):
            name = collector_node.attrib['name']
            value = "" if collector_node.text is None else collector_node.text
            config._collectors.append( (name, value, filename) )

        return config

    @staticmethod
    def _load_and_verify(configfile):
        try:
            xmlroot = lxml.etree.parse(str(configfile))

            xmlschema = lxml.etree.fromstring(
                pkgutil.get_data('lbuild', 'resources/configuration.xsd'))
            schema = lxml.etree.XMLSchema(xmlschema)
            schema.assertValid(xmlroot)

            xmltree = xmlroot.getroot()
        except OSError as error:
            raise LbuildConfigException(configfile, error)
        except (lxml.etree.DocumentInvalid,
                lxml.etree.XMLSyntaxError,
                lxml.etree.XMLSchemaParseError,
                lxml.etree.XIncludeError) as error:
            # lxml.etree has the used exception, but pylint is not able to detect them:
            # pylint: disable=no-member
            raise LbuildConfigException(configfile, ": Validation failed!\n\n{}".format(error))
        return xmltree

    @staticmethod
    def _substitute_env(configfile, root, env={}):
        for i, node in enumerate(root):

            if node.text and "$" in node.text:
                # replace all occurences inside the string with lookup matches
                keys = re.findall(r'\${(.*?)}', node.text)
                for k in keys:
                    v = env.get(k, None)
                    if v:
                        node.text = node.text.replace('${%s}'%k, v)
                    else:
                        raise LbuildConfigSubstitutionException(
                                configfile, lxml.etree.tostring(node).decode("utf-8"), k)
            # recursively crawl nodes
            node = ConfigNode._substitute_env(configfile, node, env)
        return root

    @staticmethod
    def _rel_path(path, configpath):
        if not os.path.isabs(path):
            path = join(configpath, path)
        return realpath(path)

    @staticmethod
    def to_dict(xmltree):
        """
        Convert XML to a Python dictionary according to
        http://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html
        """
        root_dict = {xmltree.tag: {} if xmltree.attrib else None}

        children = []
        for node in xmltree:
            children.append(node)

        if children:
            dd = collections.defaultdict(list)
            for dc in [ConfigNode.to_dict(node) for node in children]:
                for key, value in dc.items():
                    dd[key].append(value)
            root_dict = {xmltree.tag: {key: value[0] if len(value) == 1 else value
                                       for key, value in dd.items()}}

        if xmltree.attrib:
            root_dict[xmltree.tag].update(
                ('@' + key, value) for key, value in xmltree.attrib.items())

        if xmltree.text:
            text = xmltree.text.strip()
            if children or xmltree.attrib:
                if text:
                    root_dict[xmltree.tag]['#text'] = text
            else:
                root_dict[xmltree.tag] = text

        return root_dict
