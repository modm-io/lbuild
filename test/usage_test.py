#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

"""
Builds a small hardware library the way large lbuild libraries are structured:
a device option deciding which modules exist, modules generated from classes,
board configurations, collectors feeding a build system generator and a
second repository on top of it all.

The tests only look at what a user would see: the generated files, the
build log, the exceptions and the command line output.
"""

import io
import os
import re
import sys
import json
import shutil
import logging
import tempfile
import unittest
import contextlib
import unittest.mock
from os.path import join

import lxml.etree

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.main
import lbuild.exception as le

RESOURCES = join(os.path.dirname(os.path.realpath(__file__)), "resources", "usage")


class UsageTestCase(unittest.TestCase):

    def setUp(self):
        # realpath, since lbuild resolves symlinks in all its paths
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(RESOURCES, self.root, dirs_exist_ok=True)
        self.project = join(self.root, "project")

        # lbuild keeps these settings in module globals
        for module, name in ((lbuild.format, "PLAIN"),
                             (lbuild.format, "WIDTH"),
                             (lbuild.format, "SHOW_NODES"),
                             (lbuild.environment, "SIMULATE"),
                             (lbuild.environment, "SYMLINK_ON_COPY"),
                             (lbuild.facade, "VERBOSE_DEPRECATION")):
            value = getattr(module, name)
            self.addCleanup(setattr, module, name, set(value) if isinstance(value, set) else value)
        lbuild.format.PLAIN = True
        # otherwise depends on the size of the terminal
        lbuild.format.WIDTH = 100

        # lbuild is run from within the project folder
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.project)

    def builder(self, *options, config="project.xml", cwd=None, **kw):
        if cwd is not None:
            os.chdir(cwd)
        return lbuild.api.Builder(cwd=os.getcwd(), config=config, options=list(options), **kw)

    def build(self, *options, modules=None, **kw):
        builder = self.builder(*options, **kw)
        builder.load()
        return builder.build(modules=modules)

    def files(self, path=""):
        """All files in the project folder, relative to the project folder."""
        path = join(self.project, path)
        return sorted(os.path.relpath(join(base, name), path)
                      for base, _, names in os.walk(path) for name in names)

    def read(self, *path):
        with open(join(self.project, *path)) as file:
            return file.read()

    def report(self):
        return json.loads(self.read("generated/hal/report.json"))


class ConfigurationTest(UsageTestCase):

    def test_should_merge_all_configurations(self):
        builder = self.builder()
        builder.load()
        config = builder.parser.config

        self.assertEqual(join(self.project, "generated"), builder.outpath)
        self.assertEqual({join(self.root, "hal/repo.lb"), join(self.root, "app/repo.lb")},
                         set(config.repositories))
        # project.xml, the lbuild.xml above it and the inherited board configuration
        self.assertEqual({"hal:board:alpha", "hal:build:make", "hal:math:*", "app:demo"},
                         set(config.modules))
        self.assertEqual({"hal:target": "arm32f4-rev2",
                          "hal:build:info": "all",
                          "hal:build:project.name": "project",
                          "hal:build:build.path": "../build/project",
                          "hal:core:stack_size": "4Ki",
                          "hal:math:tables": "sine, sine, log",
                          "hal:math:precision": "8, 16"},
                         {name: value for name, (value, _) in config.options.items()})
        self.assertEqual([("hal:build:define", "FROM_BASE_CONFIG=1"),
                          ("hal:build:define", "FROM_PROJECT=2")],
                         sorted((name, value) for name, value, _ in config.collectors))

    def test_should_remember_where_an_option_was_set(self):
        builder = self.builder("hal:core:with_heap=yes")
        builder.load()
        sources = {name: filename for name, (_, filename) in builder.parser.config.options.items()}

        self.assertEqual(join(self.project, "project.xml"), sources["hal:core:stack_size"])
        self.assertEqual(join(self.root, "lbuild.xml"), sources["hal:build:info"])
        self.assertEqual(join(self.root, "hal/src/board/alpha/board.xml"), sources["hal:target"])
        self.assertEqual(join(os.getcwd(), "command-line"), sources["hal:core:with_heap"])

    def test_should_select_configuration_revision(self):
        for alias, revision in (("hal:alpha", "2"), ("hal:alpha:rev2", "2"), ("hal:alpha:rev1", "1")):
            builder = self.builder(config=alias, cwd=self.root)
            builder.load(join(self.root, "hal/repo.lb"))

            self.assertEqual(revision, builder.parser.find_option("hal:target").value.revision)
            self.assertEqual(["hal:board:alpha"], builder.parser.config.modules)

    def test_should_not_find_unknown_configuration(self):
        builder = self.builder(config="hal:gamma", cwd=self.root)
        with self.assertRaises(le.LbuildConfigAliasNotFoundException):
            builder.load(join(self.root, "hal/repo.lb"))

    @unittest.expectedFailure
    def test_should_not_find_unknown_configuration_revision(self):
        # FIXME: raises a KeyError instead
        builder = self.builder(config="hal:alpha:rev3", cwd=self.root)
        with self.assertRaises(le.LbuildException):
            builder.load(join(self.root, "hal/repo.lb"))

    def test_should_require_repositories(self):
        builder = self.builder(config="hal:alpha", cwd=tempfile.gettempdir())
        with self.assertRaises(le.LbuildConfigNoReposException):
            builder.load()

    def test_should_relocate_path_options_to_their_configuration(self):
        builder = self.builder()
        builder.load()
        # Set in project.xml, so relative to the project folder
        self.assertEqual(join(self.root, "build/project"),
                         builder.parser.find_option("hal:build:build.path").value)
        # Empty paths are not relocated
        self.assertEqual("", builder.parser.find_option("hal:build:image.source").value)

        builder = self.builder("hal:build:image.source=images")
        builder.load()
        # Set on the command line, so relative to the working directory
        self.assertEqual(join(os.getcwd(), "images"),
                         builder.parser.find_option("hal:build:image.source").value)


class DeviceTest(UsageTestCase):

    MODULES = {
        "arm32f4": {"hal:board", "hal:board:alpha", "hal:build", "hal:build:make", "hal:core",
                    "hal:heap", "hal:math", "hal:math:filter", "hal:uart", "hal:uart:1",
                    "hal:uart:2"},
        "avr8a": {"hal:board", "hal:board:beta", "hal:build", "hal:build:make", "hal:core",
                  "hal:math", "hal:math:filter", "hal:uart", "hal:uart:0"},
        "host": {"hal:board", "hal:build", "hal:build:make", "hal:core", "hal:heap",
                 "hal:math", "hal:math:filter"},
    }

    def load(self, *options):
        builder = self.builder(*options, config=None, cwd=self.root)
        builder.load()
        return builder.parser

    def test_should_only_offer_modules_for_the_device(self):
        for device, modules in self.MODULES.items():
            parser = self.load("hal:target=" + device)
            self.assertEqual(modules, set(parser.modules), device)

    def test_should_only_offer_options_for_the_device(self):
        self.assertIn("hal:core:vectors", self.load("hal:target=arm32f4").module_options)
        self.assertNotIn("hal:core:vectors", self.load("hal:target=avr8a").module_options)

    def test_should_only_offer_collectors_for_the_device(self):
        def collectors(device):
            parser = self.load("hal:target=" + device)
            return {c.fullname for c in parser.find_module("hal:build").collectors}

        self.assertIn("hal:build:flash.script", collectors("arm32f4"))
        self.assertNotIn("hal:build:flash.script", collectors("host"))

    def test_should_convert_device_with_custom_option(self):
        option = self.load("hal:target=arm32f4xyz-rev7").find_option("hal:target")

        self.assertEqual("arm32f4", option.value.name)
        self.assertEqual("7", option.value.revision)
        self.assertEqual(["arm32f4", "avr8a", "host"], option.values)
        self.assertEqual("DeviceOption", option.class_name)

    def test_should_not_touch_unused_enumeration_values(self):
        option = self.load("hal:target=host").find_option("hal:target")
        option.format_values()
        self.assertEqual("host", option.value.name)
        # only the selected device was ever created by the option
        self.assertEqual({"host"}, set(type(option._enumeration).created))

    def test_should_reject_unknown_device(self):
        with self.assertRaises(le.LbuildParserOptionInvalidException) as error:
            self.load("hal:target=z80")
        self.assertIn("Device is unknown!", str(error.exception))

        with self.assertRaises(le.LbuildParserOptionInvalidException) as error:
            self.load("hal:target=arm")
        self.assertIn("Device is ambiguous!", str(error.exception))

    def test_should_require_device_before_loading_modules(self):
        builder = self.builder(config=None, cwd=self.root)
        builder.load()

        self.assertEqual({}, builder.parser.modules)
        self.assertEqual(["hal:target"], list(builder.parser.repo_options))
        with self.assertRaises(le.LbuildOptionRequiredInputsException):
            builder.build()

    def test_should_not_select_unavailable_module(self):
        builder = self.builder("hal:target=host", config=None, cwd=self.root)
        builder.load()
        with self.assertRaises(le.LbuildParserNodeNotFoundException):
            builder.build(modules=["hal:uart"])


class BuildTest(UsageTestCase):

    GENERATED = [
        "app/main.cpp",
        "app/repo.mk",
        "hal/repo.mk",
        "hal/report.json",
        "hal/src/board/board.hpp",
        "hal/src/core/core.hpp",
        "hal/src/core/startup.c",
        "hal/src/core/vectors_arm32f4.c",
        "hal/src/info.c",
        "hal/src/math/detail/filter.hpp",
        "hal/src/math/filter/filter.hpp",
        "hal/src/math/math.hpp",
        "hal/src/math/table_log_16.hpp",
        "hal/src/math/table_log_8.hpp",
        "hal/src/math/table_sine_16.hpp",
        "hal/src/math/table_sine_8.hpp",
        "hal/src/uart/uart_1.cpp",
        "hal/src/uart/uart_1.hpp",
        "hal/src/uart/uart_2.cpp",
        "hal/src/uart/uart_2.hpp",
        "hal/src/uart/uart_all.hpp",
        "hal/src/uart/uart_base.hpp",
        "hal/tools/flash.cfg",
        "hal/tools/size.py",
    ]

    def test_should_generate_files(self):
        buildlog = self.build()

        self.assertEqual(self.GENERATED, self.files("generated"))
        # Only the Makefile is generated outside of the output path
        self.assertEqual(["Makefile", "project.xml"],
                         [f for f in self.files() if not f.startswith("generated")])
        self.assertEqual(sorted(self.GENERATED + ["../Makefile"]),
                         sorted(op.local_filename_out() for op in buildlog.operations))

    def test_should_not_copy_ignored_files(self):
        self.build()
        generated = self.files("generated")
        # module files, repository ignore patterns, env.ignore_files() and env.ignore_paths()
        for ignored in ("math.lb", "filter.lb", "board.xml", "notes.md", "notes.tmp",
                        "math_test.cpp", "table.hpp.in"):
            self.assertFalse([f for f in generated if f.endswith(ignored)], ignored)

    def test_should_render_templates(self):
        self.build()

        self.assertEqual("// arm32f4 revision 2\n"
                         "\n"
                         "// ram: 0x10000\n"
                         "// rom: 0x10000\n"
                         "\n"
                         "static char stack[4096];\n"
                         "// included for arm32f4",
                         self.read("generated/hal/src/core/startup.c"))
        # local filters are combined with the filters of the repository
        self.assertEqual("// location 0\n"
                         "// vector 0 at 0x0000\n"
                         "// vector 1 at 0x0004\n"
                         "// vector 2 at 0x0008\n",
                         self.read("generated/hal/src/core/vectors_arm32f4.c"))
        self.assertEqual("// Uart2 with 115200 baud", self.read("generated/hal/src/uart/uart_2.hpp"))
        self.assertEqual("// logger: True, target: arm32f4",
                         self.read("generated/hal/src/board/board.hpp"))
        self.assertEqual("// info level: all, built True", self.read("generated/hal/src/info.c"))
        self.assertEqual("// log table with 16 bits",
                         self.read("generated/hal/src/math/table_log_16.hpp"))

    def test_should_copy_files_unchanged(self):
        self.build()
        self.assertEqual("// filter.hpp\n", self.read("generated/hal/src/math/filter/filter.hpp"))
        self.assertEqual("// math.hpp\n",
                         self.read("generated/hal/src/math/math.hpp"))

    def test_should_build_submodules_before_their_parent(self):
        self.build()
        self.assertEqual('#ifndef HAL_UART_ALL_HPP\n'
                         '#include "uart_1.hpp"\n'
                         '#include "uart_2.hpp"\n'
                         '#include "uart_base.hpp"\n'
                         '#endif',
                         self.read("generated/hal/src/uart/uart_all.hpp"))

    def test_should_collect_values_per_repository(self):
        self.build()
        report = self.report()

        self.assertEqual(["app", "hal"], sorted(report["repositories"]))
        app, hal = report["repositories"]["app"], report["repositories"]["hal"]
        # paths are made relative to the repository folder
        self.assertEqual(["."], app["includes"])
        self.assertEqual(["src", "src/board"], sorted(hal["includes"]))
        # Values from the configuration files belong to the repository of the collector
        self.assertEqual(["BOARD_ALPHA", "FROM_BASE_CONFIG=1", "FROM_PROJECT=2"],
                         sorted(hal["defines"]))
        self.assertEqual([], app["defines"])
        self.assertEqual(["BOARD_ALPHA", "FROM_BASE_CONFIG=1", "FROM_PROJECT=2"],
                         sorted(report["defines"]))

    def test_should_provide_paths_and_queries_in_post_build(self):
        self.build()
        report = self.report()

        self.assertEqual("project", report["name"])
        self.assertEqual("generated", report["output"])
        self.assertEqual("../build/project", report["build_path"])
        self.assertEqual("", report["image_path"])
        self.assertEqual(4, report["jobs"])
        self.assertEqual(["hal/tools/flash.cfg"], report["flash"])
        self.assertEqual([{"name": "ram", "size": 65536}, {"name": "rom", "size": 65536}],
                         report["memories"])
        self.assertTrue(report["has_uart"])

    def test_should_use_defaults_for_missing_collectors_and_modules(self):
        # Only uses the lbuild.xml in the folder above
        self.build("hal:target=host", config=None, modules=["hal:math"])
        with open(join(self.project, "hal/report.json")) as file:
            report = json.load(file)

        self.assertEqual(1, report["jobs"])
        self.assertEqual([], report["flash"])
        self.assertEqual([], report["memories"])
        self.assertFalse(report["has_uart"])
        self.assertEqual("project", report["name"])
        self.assertEqual(".", report["output"])

    def test_should_generate_build_system(self):
        self.build()

        self.assertEqual("NAME := project\n"
                         "include generated/app/repo.mk\n"
                         "include generated/hal/repo.mk\n",
                         self.read("Makefile"))
        self.assertEqual("# app\n"
                         "SOURCES += main.cpp\n"
                         "\n"
                         "FLAGS :=\n",
                         self.read("generated/app/repo.mk"))
        # flags collected for specific files and callables collected as formatters
        self.assertEqual("# hal\n"
                         "SOURCES += src/core/startup.c [-fno-builtin]\n\n"
                         "SOURCES += src/core/vectors_arm32f4.c\n\n"
                         "SOURCES += src/info.c\n\n"
                         "SOURCES += src/uart/uart_1.cpp\n\n"
                         "SOURCES += src/uart/uart_2.cpp\n\n"
                         "FLAGS := $(DEFINE)INFO\n",
                         self.read("generated/hal/repo.mk"))

    def test_should_not_generate_optional_files(self):
        self.build("hal:build:make:include_makefile=no", "hal:build:info=off")

        self.assertNotIn("Makefile", self.files())
        self.assertNotIn("hal/src/info.c", self.files("generated"))
        self.assertIn("FLAGS :=\n", self.read("generated/hal/repo.mk"))

    def test_should_log_operations(self):
        buildlog = self.build()

        self.assertEqual(["app", "hal"], sorted(buildlog.repositories))
        self.assertEqual(["app:demo", "hal:board:alpha", "hal:build", "hal:build:make", "hal:core",
                          "hal:math", "hal:math:filter", "hal:uart", "hal:uart:1", "hal:uart:2"],
                         buildlog.modules)
        # includes the operations of the submodules
        self.assertEqual(["hal/src/uart/uart_1.cpp", "hal/src/uart/uart_1.hpp",
                          "hal/src/uart/uart_2.cpp", "hal/src/uart/uart_2.hpp",
                          "hal/src/uart/uart_all.hpp", "hal/src/uart/uart_base.hpp"],
                         sorted(op.local_filename_out()
                                for op in buildlog.operations_per_module("hal:uart")))

        operation = buildlog.operations_per_module("hal:board:alpha")[0]
        self.assertEqual("hal:board:alpha", operation.module_name)
        self.assertEqual(join(self.root, "hal/src/board/alpha/board.hpp.in"), operation.filename_in)
        self.assertEqual(join(self.project, "generated/hal/src/board/board.hpp"),
                         operation.filename_out)
        self.assertEqual("board.hpp.in", operation.local_filename_in())
        self.assertEqual("src/board/board.hpp", operation.local_filename_out("hal"))

    def assertSerializable(self, buildlog, path):
        restored = lbuild.buildlog.BuildLog.from_xml(buildlog.to_xml(path=path), path=path)

        self.assertEqual(buildlog.modules, restored.modules)
        self.assertEqual([(op.module_name, op.filename_in, op.filename_out)
                          for op in buildlog.operations],
                         [(op.module_name, op.filename_in, op.filename_out)
                          for op in restored.operations])

    def test_should_serialize_buildlog(self):
        buildlog = self.build("hal:target=host", config=None, modules=["hal:math"])
        self.assertSerializable(buildlog, self.project)

    @unittest.expectedFailure
    def test_should_serialize_buildlog_with_output_path(self):
        # FIXME: the paths are stored relative to the working directory, but
        # restored relative to the output path
        self.assertSerializable(self.build(), self.project)

    @unittest.expectedFailure
    def test_should_simulate_build_without_creating_folders(self):
        # FIXME: the folders of copied files are created
        builder = self.builder()
        builder.load()
        builder.build(simulate=True)
        self.assertEqual(["project.xml"], os.listdir(self.project))

    def test_should_resolve_dependencies(self):
        builder = self.builder("hal:target=arm32f4", config=None, cwd=self.root)
        builder.load(join(self.root, "app/repo.lb"))
        modules, _ = builder.validate(["app:demo"])

        # the make module is requested by the configuration
        self.assertEqual(["app:demo", "hal:build", "hal:build:make", "hal:math"],
                         sorted(m.fullname for m in modules))

    def test_should_resolve_option_dependencies(self):
        def built(*options):
            return set(self.build(*options).modules)

        self.assertIn("hal:uart:2", built())
        self.assertNotIn("hal:uart:2", built("hal:board:alpha:with_logger=no"))
        self.assertNotIn("hal:heap", built())
        self.assertIn("hal:heap", built("hal:core:with_heap=yes"))

    def test_should_see_modules_added_by_dependencies(self):
        self.build("hal:core:with_heap=yes")

        self.assertIn("#define HAS_HEAP", self.read("generated/hal/src/core/startup.c"))
        self.assertEqual(["heap"], self.report()["repositories"]["hal"]["libraries"])
        self.assertEqual(["hal/src/heap/pool/pool.cpp", "hal/src/heap/pool/pool.hpp"],
                         [f for f in self.files("generated") if "heap" in f])

    def test_should_build_configuration_alias(self):
        builder = self.builder("hal:build:make:include_makefile=no", config="hal:beta",
                               cwd=self.root, outpath=join(self.root, "out"))
        builder.load(join(self.root, "hal/repo.lb"))
        buildlog = builder.build()

        self.assertEqual(["hal:board:beta", "hal:core", "hal:uart", "hal:uart:0"],
                         buildlog.modules)
        with open(join(self.root, "out/hal/src/core/startup.c")) as file:
            self.assertTrue(file.read().startswith("// avr8a\n"))

    @unittest.expectedFailure
    def test_should_generate_into_working_directory_of_builder(self):
        # FIXME: the output path defaults to the working directory of the
        # process and not to the one passed to the builder
        os.mkdir(join(self.root, "elsewhere"))
        os.chdir(join(self.root, "elsewhere"))
        builder = lbuild.api.Builder(cwd=self.root, options=["hal:target=host"])
        builder.load()
        builder.build(modules=["hal:math"])
        self.assertTrue(os.path.isfile(join(self.root, "hal/report.json")))

    @unittest.expectedFailure
    def test_should_not_generate_over_its_own_sources(self):
        # FIXME: a file that is copied onto itself gets deleted
        builder = self.builder("hal:target=host", config=None, cwd=self.root)
        builder.load()
        try:
            builder.build(modules=["hal:math"])
        except le.LbuildException:
            pass
        self.assertTrue(os.path.isfile(join(self.root, "hal/src/math/math.hpp")))

    def test_should_overwrite_previous_build(self):
        self.build()
        self.build("hal:core:stack_size=8Ki")
        self.assertIn("stack[8192]", self.read("generated/hal/src/core/startup.c"))

    def test_should_simulate_build(self):
        builder = self.builder()
        builder.load()
        buildlog = builder.build(simulate=True)

        self.assertEqual(sorted(self.GENERATED + ["../Makefile"]),
                         sorted(op.local_filename_out() for op in buildlog.operations))
        self.assertEqual(["project.xml"], self.files())

    def test_should_symlink_copied_files(self):
        builder = self.builder()
        builder.load()
        builder.build(use_symlinks=True)

        copied = join(self.project, "generated/hal/src/core/core.hpp")
        self.assertTrue(os.path.islink(copied))
        self.assertEqual(join(self.root, "hal/src/core/core.hpp"), os.path.realpath(copied))
        # templates cannot be linked
        self.assertFalse(os.path.islink(join(self.project, "generated/hal/src/core/startup.c")))


class ValidateTest(UsageTestCase):

    def validate(self, *options):
        builder = self.builder(*options)
        builder.load()
        return builder.validate()

    def assertInvalid(self, *options):
        with self.assertRaises(le.LbuildAggregateException) as error:
            self.validate(*options)
        return [str(e) for e in error.exception.exceptions]

    def test_should_validate(self):
        modules, _ = self.validate()
        self.assertEqual(["app:demo", "hal:board", "hal:board:alpha", "hal:build", "hal:build:make",
                          "hal:core", "hal:math", "hal:math:filter", "hal:uart", "hal:uart:1",
                          "hal:uart:2"],
                         sorted(m.fullname for m in modules))

    def test_should_validate_option_input(self):
        for option, reason in (("hal:core:stack_size=1001", "Stack must be 8-byte aligned!"),
                               ("hal:core:stack_size=128", "greater or equal to '256'"),
                               ("hal:core:stack_size=1Mi", "smaller or equal to '65536'"),
                               ("hal:core:stack_size=much", "Input must be numeric!"),
                               ("hal:core:with_heap=maybe", "Input must be boolean!"),
                               ("hal:core:vectors=flash", "element of the enumeration"),
                               ("hal:math:tables=sine,cosine", "element of the enumeration"),
                               ("hal:math:precision=8,many", "Input must be numeric!")):
            with self.assertRaises(le.LbuildParserOptionInvalidException, msg=option) as error:
                self.validate(option)
            self.assertIn(reason, str(error.exception))

    @unittest.expectedFailure
    def test_should_validate_range_of_list_option_input(self):
        # FIXME: set and list options do not check the limits of a NumericOption
        with self.assertRaises(le.LbuildParserOptionInvalidException):
            self.validate("hal:math:precision=8,64")

    def test_should_not_know_option(self):
        with self.assertRaises(le.LbuildParserNodeNotFoundException):
            self.validate("hal:core:heap_size=1Ki")

    def test_should_fail_in_module_function(self):
        errors = self.assertInvalid("hal:core:vectors=ram", "hal:core:stack_size=256")
        self.assertEqual(1, len(errors))
        self.assertIn("Vector table does not fit into 4096 bytes of RAM!", errors[0])
        self.assertIn("hal:core", errors[0])

    def test_should_fail_in_module_class(self):
        errors = self.assertInvalid("hal:uart:2:baudrate=2M")
        self.assertEqual(1, len(errors))
        self.assertIn("Uart2 cannot do 2000000 baud!", errors[0])

    def test_should_report_all_failures(self):
        errors = self.assertInvalid("hal:uart:1:baudrate=2M", "hal:uart:2:baudrate=3M",
                                    "hal:core:vectors=ram", "hal:core:stack_size=256")
        self.assertEqual(3, len(errors))

    def test_should_not_build_after_failed_validation(self):
        with self.assertRaises(le.LbuildAggregateException):
            self.build("hal:uart:2:baudrate=2M")
        self.assertEqual(["project.xml"], self.files())

    def test_should_log_from_module(self):
        with self.assertLogs("user.hal.core", logging.WARNING) as logs:
            self.validate("hal:core:stack_size=256")
        self.assertEqual(["WARNING:user.hal.core:A stack of 256 bytes is very small!"], logs.output)

        with self.assertLogs("user.app.demo", logging.INFO) as logs:
            self.validate()
        self.assertEqual(1, len(logs.output))
        self.assertIn("Tables: ", logs.output[0])

    def test_should_warn_about_undeclared_dependency(self):
        with self.assertLogs("lbuild.node", logging.WARNING) as logs:
            self.validate()
        self.assertEqual(["WARNING:lbuild.node:Module 'hal:build' accessing 'hal:core:memories' "
                          "without depending on 'hal:core'!"], logs.output)

    def test_should_forward_moved_option(self):
        with self.assertLogs("lbuild.node", logging.WARNING) as logs:
            self.build("hal:build:make:info=git", "hal:build:make:project.name=moved")

        self.assertEqual("// info level: git, built True", self.read("generated/hal/src/info.c"))
        self.assertEqual("moved", self.report()["name"])
        self.assertIn("NAME := moved\n", self.read("Makefile"))
        moved = [log for log in logs.output if "has been moved" in log]
        self.assertIn("'hal:build:make:info' has been moved to ':build:info'", moved[0] + moved[-1])
        self.assertIn("Moved into the build module", moved[0])

    def test_should_refuse_removed_option(self):
        with self.assertRaises(le.LbuildResolverAliasException) as error:
            self.validate("hal:uart:1:buffer.tx=16")
        self.assertIn("Use a template argument instead.", str(error.exception))

    def test_should_validate_collector_input(self):
        for collector, reason in (("hal:build:cflags=O2", "Flags must start with '-'!"),
                                  ("hal:build:library=libm.a", "Only pass the name of the library!"),
                                  ("hal:build:jobs=0", "greater or equal to '1'")):
            builder = self.builder(collectors=[collector])
            builder.load()
            with self.assertRaises(le.LbuildParserOptionInvalidException, msg=collector) as error:
                builder.validate()
            self.assertIn(reason, str(error.exception))

    def test_should_not_know_collector(self):
        builder = self.builder(collectors=["hal:build:ldflags=-lm"])
        builder.load()
        with self.assertRaises(le.LbuildParserNodeNotFoundException):
            builder.validate()

    def test_should_collect_from_command_line(self):
        builder = self.builder(collectors=["hal:build:define=FROM_CLI", "hal:build:cflags=-O2"])
        builder.load()
        builder.build()

        self.assertIn("FROM_CLI", self.report()["defines"])
        self.assertIn("FLAGS := -O2 $(DEFINE)INFO\n", self.read("generated/hal/repo.mk"))


class DescriptionTest(UsageTestCase):

    def setUp(self):
        super().setUp()
        builder = self.builder()
        builder.load()
        self.parser = builder.parser

    def test_should_read_description_from_file(self):
        description = self.parser.find_any("hal")[0].description
        self.assertIn(">> hal  [Repository]", description)
        self.assertIn("Generates drivers for exactly the device you ask for.", description)

    def test_should_format_descriptions_of_repository_and_modules(self):
        # The formatter of the repository is inherited by all of its nodes
        self.assertIn("A TINY HARDWARE ABSTRACTION LIBRARY",
                      self.parser.find_any("hal")[0].description)
        self.assertIn("\nCORE\n", self.parser.find_module("hal:core").description)
        self.assertIn("\nMATH\n", self.parser.find_module("hal:math").description)
        self.assertIn("\nTARGET DEVICE\n", self.parser.find_option("hal:target").description)
        # but not by other repositories
        self.assertIn("Demo application", self.parser.find_module("app:demo").description)

    def test_should_format_short_descriptions(self):
        self.assertEqual("A tiny hardware abstraction library",
                         self.parser.find_any("hal")[0].short_description)
        self.assertEqual("Core", self.parser.find_module("hal:core").short_description)
        self.assertEqual("Target device", self.parser.find_option("hal:target").short_description)

    def test_should_describe_lazy_description(self):
        description = self.parser.find_module("hal:build").description
        self.assertIn("Collects everything the build system generators need to know.", description)
        # the global repopath() is absolute, unlike env.repopath()
        self.assertIn("Scripts live in " + join(self.root, "hal/tools/scripts"), description)

    def test_should_describe_children(self):
        description = self.parser.find_module("hal:core").description
        self.assertIn(">>>> hal:core:stack_size  [NumericOption]", description)
        self.assertIn("Value: 4Ki (4096)\nInputs: [256 .. 3Ki .. 64Ki]", description)
        self.assertIn(">>>> hal:core:vectors  [EnumerationOption]", description)
        self.assertIn("Value: rom\nInputs: [ram, rom]", description)
        self.assertIn("Value: no\nInputs: [yes, no]", description)

    def test_should_describe_set_options(self):
        description = self.parser.find_option("hal:math:tables").description
        self.assertIn("[EnumerationSetOption]", description)
        self.assertIn("Value: {log, sine}\nInputs: [gamma, log, sine]", description)

        description = self.parser.find_option("hal:math:precision").description
        self.assertIn("[NumericListOption]", description)
        self.assertIn("Value: [16, 8]\nInputs: [1 ... 32]", description)

    def test_should_describe_queries(self):
        query = self.parser.find_any("hal:core:align")[0]
        self.assertIn(">> hal:core:align(value, alignment=8)  [Query]", query.description)
        self.assertIn("Rounds the value up to the next multiple of the alignment.",
                      query.description)

        query = self.parser.find_any("hal:core:memories")[0]
        self.assertIn(">> hal:core:memories  [EnvironmentQuery]", query.description)
        self.assertIn(":returns: list of memory dictionaries", query.description)

    def test_should_describe_collectors_and_configurations(self):
        self.assertIn(">> hal:build:path.include  [PathCollector]\n\n"
                      "Search paths for header files\n\nInputs: [Path]",
                      self.parser.find_any("hal:build:path.include")[0].description)
        self.assertIn("Inputs: [Callable]",
                      self.parser.find_any("hal:build:make:flag_format")[0].description)
        self.assertIn("Inputs: [1 ... +Inf]", self.parser.find_any("hal:build:jobs")[0].description)
        self.assertIn(">> hal:alpha  [Configuration]\n\nBoard alpha\n\n"
                      "Version: rev2\nVersions: [rev1, rev2]",
                      self.parser.find_any("hal:alpha")[0].description)

    def test_should_find_nodes_with_wildcards(self):
        def find(query):
            return sorted(n.fullname for n in self.parser.find_modules(query))

        self.assertEqual(["hal:uart:1", "hal:uart:2"], find("hal:uart:*"))
        self.assertEqual(["hal:uart:1", "hal:uart:2"], find(":uart:*"))
        self.assertEqual(["hal:uart", "hal:uart:1", "hal:uart:2"], find("hal:uart:**"))
        self.assertEqual(["hal:board:alpha", "hal:build:make", "hal:math:filter", "hal:uart:1",
                          "hal:uart:2"], find("hal:*:*"))
        self.assertEqual(["app:demo"], find("app:*"))
        self.assertEqual(["app:demo", "hal:board", "hal:build", "hal:core", "hal:heap", "hal:math",
                          "hal:uart"], find("*:*"))
        with self.assertRaises(le.LbuildParserNodeNotFoundException):
            find("hal:spi")


class CommandLineTest(UsageTestCase):

    def setUp(self):
        super().setUp()
        # The command line tool configures the root logger
        root = logging.getLogger()
        self.addCleanup(setattr, root, "handlers", list(root.handlers))
        self.addCleanup(root.setLevel, root.level)
        self.addCleanup(lbuild.logger.CallCounter.levels.clear)
        lbuild.logger.CallCounter.levels.clear()

    def run_lbuild(self, *arguments, plain=True):
        """Returns what lbuild prints to the standard output."""
        args = lbuild.main.prepare_argument_parser().parse_args(list(arguments))
        # otherwise depends on whether the tests are run in a terminal
        args.plain = plain
        with contextlib.redirect_stderr(io.StringIO()):
            return lbuild.main.run(args)

    def main(self, *arguments):
        """Returns the exit code, the standard output and the standard error."""
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with unittest.mock.patch.object(sys, "argv", ["lbuild", "--plain"] + list(arguments)), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                lbuild.main.main()
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_should_discover_tree(self):
        tree = self.run_lbuild("discover").splitlines()

        self.assertEqual("Parser(lbuild)", tree[0].strip())
        self.assertEqual([
            "Repository(app @ ../app)   Application modules living outside of the library",
            "Module(app:demo)   Demo application",
            "Repository(hal @ ../hal)   A tiny hardware abstraction library",
            "Option(target) = arm32f4-rev2 in [arm32f4, avr8a, host]   Target device",
            "Config(hal:alpha:rev2) in [rev1, rev2]   Board alpha",
            "Config(hal:beta)   Board beta",
            "Module(hal:board)   Board support packages",
            "Module(hal:board:alpha)   Alpha board",
            "Option(with_logger) = yes in [yes, no]   Log to the on-board serial adapter",
            "Module(hal:build)   Build system",
        ], [line.lstrip(" │├╰─") for line in tree[1:11]])
        self.assertIn("Option(tables) = {log, sine} in [gamma, log, sine]   Tables to generate",
                      [line.lstrip(" │├╰─") for line in tree])
        # Queries, collectors and aliases are only for developers
        self.assertFalse([line for line in tree if "Query(" in line or "Alias(" in line])

    def test_should_discover_tree_before_device_is_known(self):
        os.chdir(self.root)
        tree = self.run_lbuild("discover")

        self.assertIn("Option(target) = REQUIRED in [arm32f4, avr8a, host]", tree)
        self.assertNotIn("Module(", tree)

    def test_should_discover_developer_tree(self):
        tree = [line.lstrip(" │├╰─")
                for line in self.run_lbuild("discover", "--developer", "-t", "hal:build").splitlines()]

        self.assertEqual("Module(hal:build)   Build system", tree[0])
        self.assertIn("Query(collect_flags)   Sorts the compile flags by the file they apply to", tree)
        self.assertIn("Collector(jobs) in [1 ... +Inf]   Parallel compile jobs", tree)
        self.assertIn("Alias(info) -> :build:info   Moved into the build module", tree)

    def test_should_discover_descriptions(self):
        output = self.run_lbuild("discover", "hal:core", "-n", "hal:heap")
        self.assertIn(">> hal:core  [Module]\n\nCORE\n", output)
        self.assertIn(">> hal:heap  [Module]\n\nDynamic memory", output)

    def test_should_discover_option_values(self):
        self.assertEqual("off\ngit\nall", self.run_lbuild("discover", "--values", "hal:build:info"))
        self.assertEqual("256\n64Ki", self.run_lbuild("discover", "--values", "hal:core:stack_size"))
        self.assertEqual("yes\nno", self.run_lbuild("discover", "--values", "hal:core:with_heap"))
        self.assertEqual("arm32f4\navr8a\nhost", self.run_lbuild("discover", "--values", "hal:target"))

    def test_should_discover_options(self):
        output = self.run_lbuild("discover-options")
        self.assertTrue(output.startswith("hal:target = arm32f4-rev2 in [arm32f4, avr8a, host]\n\n"
                                          "  Target device\n"))
        self.assertIn("hal:core:stack_size = 4Ki (4096) in [256 .. 3Ki .. 64Ki]\n\n"
                      "  Size of the main stack in bytes\n", output)
        self.assertIn("hal:build:build.path = ../build/project in [Path: build]", output)
        self.assertIn("hal:build:image.source = [] in [Path]", output)
        self.assertIn("hal:uart:2:baudrate = 115200 in [1200 .. 115200 .. +Inf]", output)

        output = self.run_lbuild("discover-options", "hal:uart:*", "-n", "hal:math")
        self.assertEqual(["hal:math:precision", "hal:math:tables", "hal:uart:1:baudrate",
                          "hal:uart:2:baudrate"],
                         [line.split(" = ")[0] for line in output.splitlines() if " = " in line])

    def test_should_search_descriptions(self):
        output = self.run_lbuild("search", "stack", "serial adapter")

        tree, _, matches = output.partition("\n\n\n")
        self.assertEqual(["Parser(lbuild)", "Repository(hal @ ../hal)", "Module(hal:board)",
                          "Module(hal:board:alpha)", "Option(with_logger)", "Module(hal:core)",
                          "Option(stack_size)"],
                         [line.lstrip(" │├╰─").split(" ")[0] + ("" if "@" not in line else " @ ../hal)")
                          for line in tree.splitlines()])
        self.assertIn(">> hal:core:stack_size  [NumericOption]\n\n"
                      "  1  Size of the main stack in bytes", matches)
        self.assertIn(">> hal:board:alpha:with_logger  [BooleanOption]", matches)

    def test_should_style_output_for_terminals(self):
        def plain(text):
            return re.sub(r"\033\[[0-9;]*m", "", text)

        # the developer view is last, since it stays enabled
        for arguments in (["discover"], ["discover", "hal:core"], ["discover-options"],
                          ["discover", "hal:math:tables", "hal:build:path.include", "hal:alpha"],
                          ["discover", "--developer"]):
            styled = self.run_lbuild(*arguments, plain=False)
            self.assertIn("\033[", styled, arguments)
            self.assertEqual(self.run_lbuild(*arguments), plain(styled), arguments)

    def test_should_highlight_search_results(self):
        output = self.run_lbuild("search", "stack", plain=False)
        self.assertIn(">> \033[1mhal:core:", output)
        self.assertIn("Size of the main \033[1mstack\033[22m in bytes", output)

    def test_should_validate(self):
        self.assertEqual("Library configuration valid.\nPlease check 1 warning!",
                         self.run_lbuild("validate"))
        self.assertEqual(["project.xml"], self.files())

    def test_should_validate_strictly(self):
        with self.assertRaises(le.LbuildException) as error:
            self.run_lbuild("validate", "--strict")
        self.assertIn("Logged 1 warning!", str(error.exception))

    def test_should_validate_additional_modules(self):
        with self.assertRaises(le.LbuildAggregateException):
            self.run_lbuild("-D", "hal:core:vectors=ram", "-D", "hal:core:stack_size=256", "validate")
        # not a dependency of anything in this project
        self.assertEqual("Library configuration valid.\nPlease check 1 warning!",
                         self.run_lbuild("validate", "-m", "hal:heap"))

    def test_should_fail_validation_with_logged_errors(self):
        with open(join(self.root, "app/demo/demo.lb"), "a") as module:
            module.write("\ndef validate(env):\n    env.log.error('This is wrong')\n"
                         "    env.log.error('This is wrong as well')\n")
        with self.assertRaises(le.LbuildException) as error:
            self.run_lbuild("validate")
        self.assertIn("Logged 2 errors!", str(error.exception))

    def test_should_build(self):
        self.assertEqual("", self.run_lbuild("build"))

        self.assertEqual(BuildTest.GENERATED, self.files("generated"))
        self.assertIn("Makefile", self.files())
        log = lxml.etree.fromstring(self.read("project.xml.log").encode())
        self.assertEqual("generated", log.find("outpath").text)
        self.assertEqual(sorted([join("generated", f) for f in BuildTest.GENERATED] +
                                ["Makefile", "project.xml.log"]),
                         sorted(node.text for node in log.iter("destination")))
        self.assertEqual({"lbuild", "app:demo", "hal:core"},
                         {node.text for node in log.iter("module")} &
                         {"lbuild", "app:demo", "hal:core", "hal:heap"})

    def test_should_build_with_arguments(self):
        self.run_lbuild("-p", "out", "-D", "hal:core:with_heap=yes", "--collect",
                        "hal:build:define=FROM_CLI", "build", "--no-log", "-m", "hal:core")

        self.assertNotIn("project.xml.log", self.files())
        self.assertEqual([], self.files("generated"))
        self.assertIn("hal/src/heap/pool/pool.hpp", self.files("out"))
        self.assertIn("FROM_CLI", json.loads(self.read("out/hal/report.json"))["defines"])

    def test_should_build_in_other_folder(self):
        os.chdir(self.root)
        self.run_lbuild("-C", "project", "-c", "project/project.xml", "build", "--no-log")
        self.assertEqual(BuildTest.GENERATED, self.files("generated"))

    def test_should_build_configuration_with_repository_argument(self):
        os.chdir(tempfile.gettempdir())
        self.run_lbuild("-r", join(self.root, "hal/repo.lb"), "-c", "hal:beta", "-p",
                        join(self.root, "out"), "-D", "hal:build:make:include_makefile=no",
                        "build", "--no-log", "-m", "hal:build:make")
        self.assertIn("hal/src/uart/uart_0.hpp", self.files(join(self.root, "out")))

    def test_should_simulate_build(self):
        output = self.run_lbuild("build", "--simulate")
        self.assertEqual(sorted(BuildTest.GENERATED + ["../Makefile"]), output.splitlines())
        self.assertEqual(["project.xml"], self.files())

    def test_should_symlink_build(self):
        self.run_lbuild("build", "--symlink")
        self.assertTrue(os.path.islink("generated/app/main.cpp"))

    def test_should_clean(self):
        self.run_lbuild("build")
        output = self.run_lbuild("clean")

        self.assertEqual(sorted(["Removing " + join("generated", f) for f in BuildTest.GENERATED] +
                                ["Removing Makefile", "Removing project.xml.log"]),
                         output.splitlines())
        self.assertEqual(["project.xml"], self.files())
        self.assertEqual(["project.xml"], os.listdir(self.project))

    @unittest.expectedFailure
    def test_should_clean_without_buildlog(self):
        # FIXME: removes the files relative to the working directory instead of
        # the output path, which may delete unrelated files!
        self.run_lbuild("build", "--no-log")
        output = self.run_lbuild("clean")

        self.assertIn("Removing generated/hal/report.json", output.splitlines())
        self.assertEqual(["project.xml"], self.files())

    def test_should_draw_dependencies(self):
        graph = self.run_lbuild("dependencies", "-m", "app:demo").splitlines()

        self.assertEqual("digraph dependencies", graph[0])
        self.assertIn("\tsubgraph clusterhal", graph)
        self.assertIn("\tsubgraph clusterapp", graph)
        # requested modules are highlighted
        self.assertIn('\t\tapp_demo [label="demo", style="filled,bold"];', graph)
        self.assertIn('\t\thal_math [label="math", style="filled,solid"];', graph)
        self.assertIn('\t\thal_uart_1 [label="uart:\\n1", style="filled,solid"];', graph)
        self.assertEqual(["app_demo -> hal_build;", "app_demo -> hal_math;",
                          "hal_board_alpha -> hal_board;", "hal_board_alpha -> hal_core;",
                          "hal_board_alpha -> hal_uart_1;", "hal_board_alpha -> hal_uart_2;",
                          "hal_build_make -> hal_build;", "hal_math_filter -> hal_math;",
                          "hal_uart_1 -> hal_core;", "hal_uart_1 -> hal_uart;",
                          "hal_uart_2 -> hal_core;", "hal_uart_2 -> hal_uart;"],
                         [line.strip() for line in graph if "->" in line])

    @unittest.expectedFailure
    def test_should_limit_dependency_depth(self):
        # FIXME: raises since the dependencies beyond the depth are not selected
        graph = self.run_lbuild("dependencies", "-n", "1")
        self.assertIn('hal_uart_1 [label="uart:\\n1", style="filled,dashed"];', graph)
        self.assertIn("hal_board_alpha -> hal_uart_1;", graph)
        self.assertNotIn("hal_uart_1 -> hal_uart;", graph)

    def test_should_draw_all_dependencies_of_single_repository(self):
        os.chdir(self.root)
        graph = self.run_lbuild("-D", "hal:target=host", "dependencies", "-m", ":**")
        self.assertIn("\tsubgraph hal", graph)
        self.assertIn('hal_heap [label="hal:\\nheap"];', graph)
        self.assertIn("hal_heap -> hal_core;", graph)

    def test_should_not_need_remote_repositories(self):
        self.assertEqual("", self.run_lbuild("init"))
        self.assertEqual("", self.run_lbuild("update"))

    def test_should_print_output(self):
        code, stdout, stderr = self.main("discover", "--values", "hal:build:info")
        self.assertEqual((0, "off\ngit\nall\n", ""), (code, stdout, stderr))

    def test_should_exit_without_command(self):
        code, stdout, _ = self.main()
        self.assertEqual(2, code)
        self.assertIn("usage: lbuild", stdout)
        self.assertIn("No command specified!", stdout)

    def test_should_exit_with_error(self):
        code, stdout, stderr = self.main("-D", "hal:target=z80", "build")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("ERROR: ", stderr)
        self.assertIn("Device is unknown!", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_should_exit_with_traceback_when_verbose(self):
        code, _, stderr = self.main("-v", "-D", "hal:target=z80", "build")
        self.assertEqual(1, code)
        self.assertIn("Traceback", stderr)

    def test_should_print_version(self):
        code, stdout, _ = self.main("--version")
        self.assertEqual((0, "lbuild {}\n".format(lbuild.__version__)), (code, stdout))


if __name__ == '__main__':
    unittest.main()
