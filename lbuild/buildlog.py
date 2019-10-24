#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import logging
import collections
import threading
from os.path import join, relpath, dirname, normpath, basename, isabs, abspath
from pathlib import Path

import lxml.etree
import lbuild.utils

from .exception import LbuildBuildlogOverwritingFileException

LOGGER = logging.getLogger('lbuild.buildlog')

class Operation:
    """
    Representation of a build operation.

    Stores the connection between a generated file and its template and module
    from within it was generated.
    """

    def __init__(self, module_name, outpath, module_path,
                 filename_in: str, filename_out: str, time=None, metadata=None):
        self.module_name = module_name
        self.time = time
        self.metadata = collections.defaultdict(set)
        if metadata:
            for key, values in metadata.items():
                for value in lbuild.utils.listify(values):
                    self.metadata[key].add(value)

        self.outpath = abspath(outpath)
        self.inpath = abspath(module_path)

        self.filename_in = abspath(filename_in)
        self.filename_out = abspath(filename_out)
        self.filename_module = None

        self.hash_in = None
        self.hash_out = None
        self.hash_module = None

        self.mtime_in = None
        self.mtime_out = None
        self.mtime_module = None

    def compute_hash(self, module_filename=None):
        self.mtime_in, self.hash_in = lbuild.utils.hash_file(self.filename_in)
        self.mtime_out, self.hash_out = lbuild.utils.hash_file(self.filename_out)
        self.mtime_module, self.hash_module = lbuild.utils.hash_file(module_filename)
        if self.hash_module is not None:
            self.filename_module = relpath(module_filename)

    def local_filename_in(self, relative_to=None):
        path = self.inpath
        if relative_to is not None:
            path = join(path, relative_to)
        return self._local_filename(self.filename_in, path)

    def local_filename_out(self, relative_to=None):
        path = self.outpath
        if relative_to is not None:
            path = join(path, relative_to)
        return self._local_filename(self.filename_out, path)

    @staticmethod
    def _local_filename(filename, path):
        localfile = join(relpath(dirname(filename), path), basename(filename))
        return normpath(localfile)

    def __repr__(self):
        return "<{}: {} -> {}>".format(self.module_name, self.filename_in, self.filename_out)


class BuildLog:
    """
    Log of a all files being generated during the build step.

    Used to detect if a previously generated file is being overwritten by
    another module. Also allows to later find out which module has generated
    a specific file.
    """

    def __init__(self, outpath=None):
        self._operations = collections.defaultdict(list)
        self._metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        self.outpath = os.getcwd() if outpath is None else abspath(outpath)

        self._build_files = {}
        self.__lock = threading.RLock()

    def add_metadata(self, module, key, values):
        with self.__lock:
            for value in lbuild.utils.listify(values):
                self._metadata[key][module.fullname].add(value)

    @property
    def metadata(self):
        metadata = collections.defaultdict(set)
        for key, data in self._metadata.items():
            for value in data.values():
                metadata[key] |= value

        for key in metadata:
            metadata[key] = sorted(list(metadata[key]))
        return metadata

    @property
    def repo_metadata(self):
        metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        for key, data in self._metadata.items():
            for module, value in data.items():
                metadata[key][module.split(":")[0]] |= value

        for key in metadata:
            for repo in metadata[key]:
                metadata[key][repo] = sorted(list(metadata[key][repo]))
        return metadata

    @property
    def module_metadata(self):
        metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        for key, data in self._metadata.items():
            for module, value in data.items():
                metadata[key][module] |= value
        for key in metadata:
            for module in metadata[key]:
                metadata[key][module] = sorted(list(metadata[key][module]))
        return metadata

    @property
    def operation_metadata(self):
        metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        for operation in self.operations:
            for key, values in operation.metadata.items():
                metadata[key][operation.local_filename_out()] |= values

        for key in metadata:
            for filename in metadata[key]:
                metadata[key][filename] = sorted(list(metadata[key][filename]))
        return metadata

    def log(self, module, filename_in: str, filename_out: str, time=None, metadata=None):
        """
        Log the generation of a file through a module.

        Checks whether an operation would overwrite a file
        previously generated by another module and raises a build
        exception in that case.

        Args:
            module: Module which generates the module.
            filename_in: Template from which the file is generated. If
                it is a relative path, it is combined with the
                module path.
            filename_out: Path of the generated file. A relative path
                is combined with the output path set in the constructor
                of the buildlog.
            time: Time of generation (current time).
        """
        if not isabs(filename_in):
            filename_in = join(module._filepath, filename_in)
        if not isabs(filename_out):
            filename_out = join(self.outpath, filename_out)
        with self.__lock:
            operation = Operation(module.fullname, self.outpath, module._filepath,
                                  filename_in, filename_out, time, metadata)
            operation.compute_hash(module._filename)
            LOGGER.debug(str(operation))

            previous = self._build_files.get(filename_out, None)
            if previous is not None:
                raise LbuildBuildlogOverwritingFileException(
                        module.fullname, filename_out, previous.module_name)

            self._build_files[filename_out] = operation
            self._operations[module.fullname].append(operation)

        return operation

    def log_unsafe(self, modulename, filename_in, filename_out,
                   time=None, metadata=None, compute_hash=True):
        """
        Log an lbuild internal operation.

        No checking for previously generated file is performed.

        Args:
            modulename: Full module name.
        """
        operation = Operation(modulename, self.outpath, self.outpath,
                              filename_in, filename_out, time, metadata)
        if compute_hash: operation.compute_hash();
        with self.__lock:
            self._operations[modulename].append(operation)

    def operations_per_module(self, modulename: str):
        """
        Get all operations which have been performed for the given
        module and its submodules.

        Args:
            modulename: Full module name.
        """
        with self.__lock:
            operations = [self._operations.get(name, []) for name in self.modules
                          if name.startswith(modulename)]
        operations = (o for olists in operations for o in olists)
        return sorted(operations, key=lambda o: (o.module_name, o.filename_in, o.filename_out))

    @property
    def repositories(self):
        return list(set(m.split(":")[0] for m in self.modules))

    @property
    def modules(self):
        with self.__lock:
            module_names = self._operations.keys()
        return sorted(list(module_names))

    @property
    def operations(self):
        with self.__lock:
            operations = self._operations.values()
        operations = (o for olists in operations for o in olists)
        return sorted(operations, key=lambda o: (o.module_name, o.filename_in, o.filename_out))

    def compare_outpath(self):
        unmodified = []
        modified = []
        missing = []
        for op in self.operations:
            destname = op.local_filename_out()
            if os.path.exists(destname):
                mtime_out = int(os.path.getmtime(destname))
                if (op.mtime_out != mtime_out and
                    op.hash_out != lbuild.utils.hash_file(destname)[1]):
                        modified.append(destname)
                else:
                    unmodified.append(destname)
            else:
                missing.append(destname)

        return (unmodified, modified, missing)

    @staticmethod
    def from_xml(string, path):
        rootnode = lxml.etree.fromstring(string)
        outpath = join(abspath(path), rootnode.find("outpath").text)
        buildlog = BuildLog(outpath)

        for opnode in rootnode.iterfind("operation"):
            module = opnode.find("module")
            module_hash = module.get("hash", None)
            module_mtime = module.get("mtime", None)
            module = module.get("name")

            source = opnode.find("source")
            source_hash = source.get("hash", None)
            source_mtime = source.get("modified", None)
            source = join(outpath, source.text)

            destination = opnode.find("destination")
            destination_hash = destination.get("hash", None)
            destination_mtime = destination.get("modified", None)
            destination = join(outpath, destination.text)

            operation = Operation(module, outpath, path, source, destination)

            operation.hash_module = module_hash
            operation.hash_in = source_hash
            operation.hash_out = destination_hash

            operation.mtime_module = None if module_mtime is None else int(module_mtime)
            operation.mtime_in = None if source_mtime is None else int(source_mtime)
            operation.mtime_out = None if destination_mtime is None else int(destination_mtime)

            buildlog._operations[module].append(operation)

        return buildlog

    def to_xml(self, path, to_string=True):
        """
        Convert the complete build log into a XML representation.
        """
        rootnode = lxml.etree.Element("buildlog")
        extended_format=False

        with self.__lock:
            versionnode = lxml.etree.SubElement(rootnode, "version")
            versionnode.text = "2.0"
            outpathnode = lxml.etree.SubElement(rootnode, "outpath")
            outpathnode.text = relpath(self.outpath, path)
            for operation in self.operations:
                operationnode = lxml.etree.SubElement(rootnode, "operation")

                modulenode = lxml.etree.SubElement(operationnode, "module")
                if extended_format:
                    if operation.mtime_module is not None:
                        modulenode.set("modified", str(operation.mtime_module))
                    if operation.hash_module is not None:
                        modulenode.set("hash", operation.hash_module)
                    if operation.filename_module is not None:
                        modulenode.text = operation.filename_module
                modulenode.set("name", operation.module_name)

                srcnode = lxml.etree.SubElement(operationnode, "source")
                if extended_format:
                    if operation.mtime_in is not None:
                        srcnode.set("modified", str(operation.mtime_in))
                    if operation.hash_in is not None:
                        srcnode.set("hash", operation.hash_in)
                srcnode.text = relpath(operation.filename_in, path)

                destnode = lxml.etree.SubElement(operationnode, "destination")
                if operation.mtime_out is not None:
                    destnode.set("modified", str(operation.mtime_out))
                if operation.hash_out is not None:
                    destnode.set("hash", operation.hash_out)
                destnode.text = relpath(operation.filename_out, path)

                if extended_format:
                    if operation.time is not None:
                        timenode = lxml.etree.SubElement(operationnode, "time")
                        timenode.text = "{:.3f} ms".format(operation.time * 1000)

        if to_string:
            return lxml.etree.tostring(rootnode,
                                       encoding="UTF-8",
                                       pretty_print=True,
                                       xml_declaration=True,)
        return rootnode
