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
import sys
import argparse
import textwrap
import traceback

import lbuild.logger
import lbuild.vcs.common
from lbuild.format import format_option_short_description

from lbuild.api import Builder

__version__ = '1.5.0'


class InitAction:
    config_required = True

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "init",
            help="Load remote repositories into the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    @staticmethod
    def perform(_, builder):
        lbuild.vcs.common.initialize(builder.config)
        return ""


class UpdateAction:
    config_required = True

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "update",
            help="Update the content of remote repositories in the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    @staticmethod
    def perform(_, builder):
        lbuild.vcs.common.update(builder.config)
        return ""


class ManipulationActionBase:
    """
    Base class for actions that interact directly with the parser repositories.

    All subclasses must implement a `perform` function.
    """
    # pylint: disable=too-few-public-methods
    config_required = True

    def load_repositories(self, args, builder):
        builder.load(args.repositories)

        # Implemented by the subclasses, therefore not known to pylint
        # pylint: disable=no-member
        return self.perform(args, builder)


class DiscoverAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "discover",
            help="Render the available repository tree with modules and options. "
                 "You may need to provide options to see the entire tree!")
        parser.add_argument(
            "-n",
            "--name",
            dest="names",
            type=str,
            action="append",
            default=[],
            help="Select a specific repository, module or option.")
        parser.add_argument(
            "--values",
            dest="values",
            action="store_true",
            default=False,
            help="Display option values, instead of description")
        parser.set_defaults(execute_action=self.load_repositories)

    @staticmethod
    def perform(args, builder):
        if args.names:
            ostream = []
            for node in builder.parser.find_all(args.names):
                if args.values and node.type == node.Type.OPTION:
                    ostream.extend(node.values)
                else:
                    ostream.append(node.description)
            return "\n".join(ostream)

        return builder.parser.render()


class DiscoverOptionsAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "discover-options",
            help="Display all known option names, current values, allowed inputs and "
                 "short descriptions.")
        parser.add_argument(
            "-n",
            "--name",
            dest="names",
            type=str,
            action="append",
            default=[],
            help="Select a specific repository or module.")
        parser.set_defaults(execute_action=self.load_repositories)

    @staticmethod
    def perform(args, builder):
        names = args.names if args.names else ["*", ":**"]
        nodes = builder.parser.find_any(names, (builder.parser.Type.MODULE,
                                                builder.parser.Type.REPOSITORY))
        options = [o for n in nodes for o in n.options]

        ostream = []
        for option in sorted(options, key=lambda n: (n.depth, n.fullname)):
            ostream.append(format_option_short_description(option))
            if option.short_description:
                ostream.append("")
                ostream.append(textwrap.indent(option.short_description, "  "))
                ostream.append("")

        return "\n".join(ostream)


class ValidateAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "validate",
            help="Validate the library configuration and data inputs with the given options.")
        parser.add_argument(
            "-m",
            "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.set_defaults(execute_action=self.load_repositories)

    @staticmethod
    def perform(args, builder):
        builder.validate(args.modules)
        return "Library configuration valid."


class BuildAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "build",
            help="Generate the library source code blob with the given options.")
        parser.add_argument(
            "-m",
            "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.add_argument(
            "--simulate",
            dest="simulate",
            action="store_true",
            default=False,
            help="Build, but do not write any files. Prints out all generated file names.")
        parser.add_argument(
            "--no-log",
            dest="buildlog",
            action="store_false",
            default=True,
            help="Do not create a build log. This log contains all files being "
                 "generated, their source files and the module which generated "
                 "the file.")
        parser.set_defaults(execute_action=self.load_repositories)

    @staticmethod
    def perform(args, builder):
        buildlog = builder.build(args.path, args.modules, simulate=args.simulate)

        if args.simulate:
            ostream = []
            for operation in buildlog.operations:
                ostream.append(operation.local_filename_out())
            return "\n".join(sorted(ostream))

        if args.buildlog:
            configfilename = args.config
            logfilename = configfilename + ".log"
            buildlog.log_unsafe("lbuild", "buildlog.xml.in", logfilename)
            with open(logfilename, "wb") as logfile:
                logfile.write(buildlog.to_xml(to_string=True, path=os.getcwd()))

        return ""


class CleanAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "clean",
            help="Remove previously generated files.")
        parser.add_argument(
            "--buildlog",
            dest="buildlog",
            default="project.xml.log",
            help="Use the given buildlog to identify the files to remove.")
        parser.set_defaults(execute_action=self.perform)

    @staticmethod
    def perform(args, builder):
        ostream = []
        if os.path.exists(args.buildlog):
            with open(args.buildlog, "rb") as logfile:
                buildlog = lbuild.buildlog.BuildLog.from_xml(logfile.read(), path=os.getcwd())
        else:
            builder.load(args.repositories)
            buildlog = builder.build(args.path, simulate=True)

        dirs = set()
        filenames = [op.local_filename_out() for op in buildlog.operations]
        for filename in sorted(filenames):
            ostream.append("Removing " + filename)
            dirs.add(os.path.dirname(filename))
            try:
                os.remove(filename)
            except OSError:
                pass

        dirs = sorted(list(dirs), key=lambda d: d.count("/"), reverse=True)
        for directory in dirs:
            try:
                os.removedirs(directory)
            except OSError:
                pass

        return "\n".join(ostream)


class DependenciesAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser(
            "dependencies",
            help="Generate a grahpviz representation of the module dependencies.")
        parser.add_argument(
            "-m",
            "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select specific modules.")
        parser.add_argument(
            "-n",
            "--depth",
            dest="depth",
            type=int,
            default=sys.maxsize,
            help="Only show dependencies up to a specific depth. Only valid if "
                 "specific modules are selected, otherwise all modules are printed "
                 "anyways.")
        parser.set_defaults(execute_action=self.load_repositories)

    @staticmethod
    def perform(args, builder):
        selected_modules = args.modules + builder.parser.config.modules
        if not selected_modules:
            selected_modules = [":**"]
        dot_file = lbuild.builder.dependency.graphviz(builder,
                                                      selected_modules,
                                                      args.depth)
        return dot_file


def prepare_argument_parser():
    """
    Set up the argument parser for the different commands.

    Return:
    Configured ArgumentParser object.
    """
    argument_parser = argparse.ArgumentParser(
        description='Build source code libraries from modules.')
    argument_parser.add_argument(
        '-r',
        '--repository',
        metavar="REPO",
        dest='repositories',
        action='append',
        default=[],
        help="Repository file(s) which should be available for the current library. "
             "The loading of repository files from a VCS is only supported through "
             "the library configuration file.")
    argument_parser.add_argument(
        '-c',
        '--config',
        dest='config',
        default='project.xml',
        help="Project configuration file. "
             "Specifies the required repositories, modules and options "
             "(default: '%(default)s').")
    argument_parser.add_argument(
        '-p',
        '--path',
        dest='path',
        default='.',
        help="Path in which the library will be generated (default: '%(default)s').")
    argument_parser.add_argument(
        '-D',
        '--option',
        metavar='OPTION',
        dest='options',
        action='append',
        type=str,
        default=[],
        help="Additional options. Options given here will be merged with options "
             "from the configuration file and will overwrite the configuration "
             "file definitions.")
    argument_parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        dest='verbose')
    argument_parser.add_argument(
        "--plain",
        dest="plain",
        action="store_true",
        default=not sys.stdout.isatty(),
        help="Disable styled output, only output plain ASCII.")
    argument_parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s {}'.format(__version__),
        help="Print the lbuild version number and exit.")

    subparsers = argument_parser.add_subparsers(
        title="Actions",
        dest="action")

    actions = [
        DiscoverAction(),
        DiscoverOptionsAction(),
        ValidateAction(),
        BuildAction(),
        CleanAction(),

        InitAction(),
        UpdateAction(),
        DependenciesAction(),
    ]
    for action in actions:
        action.register(subparsers)

    return argument_parser


def run(args):
    lbuild.logger.configure_logger(args.verbose)
    lbuild.format.plain = args.plain

    try:
        command = args.execute_action
    except AttributeError:
        raise lbuild.exception.LbuildArgumentException("No command specified")

    builder = Builder(config=args.config, options=args.options)
    return command(args, builder)


def main():
    """
    Main entry point of lbuild.
    """
    try:
        argument_parser = prepare_argument_parser()

        commandline_arguments = sys.argv[1:]
        args = argument_parser.parse_args(commandline_arguments)
        lbuild.logger.configure_logger(args.verbose)

        output = run(args)
        print(output)
    except lbuild.exception.LbuildAggregateException as aggregate:
        for error in aggregate.exceptions:
            sys.stderr.write('\nERROR: %s\n' % error)
        sys.exit(2)
    except lbuild.exception.LbuildForwardException as error:
        sys.stderr.write("\nERROR in '{}'\n".format(error.module))
        traceback.print_exception(type(error.exception),
                                  error.exception,
                                  error.exception.__traceback__,
                                  limit=-1)
        sys.exit(4)
    except lbuild.exception.LbuildArgumentException as error:
        argument_parser.print_help()
        print(error)
        sys.exit(2)
    except lbuild.exception.LbuildTemplateException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        traceback.print_exc()
        sys.exit(3)
    except lbuild.exception.LbuildException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        if args.verbose >= 2:
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
