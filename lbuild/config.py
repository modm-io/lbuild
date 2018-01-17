#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2018, Fabian Greif
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

import lbuild.module

LOGGER = logging.getLogger('lbuild.config')
DEFAULT_CACHE_FOLDER = ".lbuild_cache"


class Option:
    """
    Option in the configuration file.
    """

    def __init__(self, name, value):
        """
        Construct a new option.

        Args:
            name: Option name. Can be not fully qualified.
            value: Value of the option.
        """
        self.name = name
        self.value = value

    def __eq__(self, other):
        return (self.name == other.name and self.value == other.value)

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return "<Option: {}={}>".format(self.name, self.value)


class Configuration:

    def __init__(self):
        self.filename = ""

        # Path to the configuration file. Use to resolve relative paths.
        self.configpath = ""

        self.options = []
        self.selected_modules = []
        self.repositories = []
        self.cachefolder = None
        self.vcs = []

    @staticmethod
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
        return xmltree

    @staticmethod
    def parse_configuration(configfile, childconfig=None):
        """
        Parse the configuration file.

        This file contains information about which modules should be included
        and how they are configured.

        Returns:
            Populated Configuration object.
        """
        if childconfig is None:
            childconfig = Configuration()

        xmltree = Configuration.load_and_verify(configfile)
        configpath = os.path.dirname(configfile)

        for basenode in xmltree.iterfind("extends"):
            basefile = Configuration.__get_path(basenode.text, configpath)
            Configuration.parse_configuration(basefile, childconfig)

        configuration = childconfig
        configuration.filename = configfile
        configuration.configpath = configpath

        # Load cachefolder
        cache_node = xmltree.find("repositories/cache")
        if cache_node is not None:
            cachefolder = Configuration.__get_path(cache_node.text, configuration.configpath)
        else:
            default = DEFAULT_CACHE_FOLDER if configuration.cachefolder is None else configuration.cachefolder
            cachefolder = os.path.join(configuration.configpath, default)
        configuration.cachefolder = cachefolder

        # Load version control nodes
        for vcs_node in xmltree.iterfind("repositories/repository/vcs"):
            for vcs in vcs_node.iterchildren():
                vcs_config = Configuration.to_dict(vcs)
                configuration.vcs.append(vcs_config)

        # Load repositories
        for path_node in xmltree.iterfind("repositories/repository/path"):
            repository_path = path_node.text.format(cache=cachefolder)

            repository_filename = os.path.realpath(os.path.join(configuration.configpath,
                                                                repository_path))

            if repository_filename not in configuration.repositories:
                configuration.repositories.append(repository_filename)

        # Load all requested modules
        for modules_node in xmltree.findall('modules'):
            for module_node in modules_node.findall('module'):
                modulename = module_node.text
                lbuild.module.verify_module_name(modulename)

                LOGGER.debug("- require module '%s'", modulename)
                if modulename not in configuration.selected_modules:
                    configuration.selected_modules.append(modulename)

        # Load options
        for option_node in xmltree.find('options').findall('option'):
            name = option_node.attrib['name']
            try:
                value = option_node.attrib['value']
            except KeyError:
                value = option_node.text

            for index, option in enumerate(configuration.options):
                if option.name == name:
                    del configuration.options[index]
            configuration.options.append(Option(name=name, value=value))

        return configuration

    @staticmethod
    def __get_path(path, configpath):
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(configpath, path)

    @staticmethod
    def format_commandline_options(cmd_options):
        cmd = []
        for option in cmd_options:
            parts = option.split('=')
            cmd.append(Option(name=parts[0], value=parts[1]))
        return cmd

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
            for dc in [Configuration.to_dict(c) for c in  children]:
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
