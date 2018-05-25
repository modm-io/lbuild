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
import colorful
import traceback

import lbuild.parser
import lbuild.logger
import lbuild.module
import lbuild.vcs.common
from lbuild.format import format_option_short_description

__version__ = '1.0.3'


class InitAction:
    config_required = True

    def register(self, argument_parser):
        parser = argument_parser.add_parser("init",
            help="Load remote repositories into the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    def perform(self, args, config):
        lbuild.vcs.common.initialize(config)
        return ""


class UpdateAction:
    config_required = True

    def register(self, argument_parser):
        parser = argument_parser.add_parser("update",
            help="Update the content of remote repositories in the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    def perform(self, args, config):
        lbuild.vcs.common.update(config)
        return ""


class ManipulationActionBase:
    """
    Base class for actions that interact directly with the parser repositories.
    """
    config_required = True

    def prepare_repositories(self, args, config):
        parser = lbuild.parser.Parser(config)
        parser.load_repositories(args.repositories)

        parser.config.add_commandline_options(args.options)
        repo_options = parser.merge_repository_options()

        return self.perform(args, parser, repo_options)


class DiscoverAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover",
            help="Render the available repository tree with modules and options. "
                 "You may need to provide options to see the entire tree!")
        parser.add_argument("-n", "--name",
            dest="names",
            type=str,
            action="append",
            default=[],
            help="Select a specific repository, module or option.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        if not len(parser._undefined_options(repo_options)):
            parser.prepare_repositories(repo_options)
            parser.merge_module_options()

        if len(args.names):
            ostream = []
            for name in args.names:
                node = parser.find(name).description
                ostream.extend([node])
            return "\n\n\n\n".join(ostream)

        return parser.render()


class DiscoverOptionsAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-options",
            help="Display all known option names, current values, allowed inputs and "
                 "short descriptions.")
        parser.add_argument("-n", "--name",
            dest="names",
            type=str,
            action="append",
            default=[],
            help="Select a specific repository or module.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        if not len(parser._undefined_options(repo_options)):
            parser.prepare_repositories(repo_options)
            parser.merge_module_options()

        names = args.names if len(args.names) else ["*", ":**"]
        nodes = parser.find_any(names, (parser.Type.MODULE, parser.Type.REPOSITORY))
        options = [o for n in nodes for o in n.options]

        ostream = []
        for option in sorted(options, key=lambda n: (n.depth, n.fullname)):
            ostream.append(format_option_short_description(option))
            if option.short_description:
                ostream.append("")
                ostream.append(textwrap.indent(option.short_description, "  "))
                ostream.append("")

        return "\n".join(ostream)


def get_modules(parser, repo_options):
    modules = parser.prepare_repositories(repo_options)
    module_options = parser.merge_module_options()
    selected_modules = parser.find_modules(parser.config.modules)
    return parser.resolve_dependencies(selected_modules)


class ValidateAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("validate",
            help="Validate the library configuration and data inputs with the given options.")
        parser.add_argument("-m", "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        parser.config.modules.extend(args.modules)
        build_modules = get_modules(parser, repo_options)
        parser.validate_modules(build_modules)
        return "Library configuration valid."


class BuildAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("build",
            help="Generate the library source code blob with the given options.")
        parser.add_argument("-m", "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.add_argument("--simulate",
            dest="simulate",
            action="store_true",
            default=False,
            help="Build, but do not write any files. Prints out all generated file names.")
        parser.add_argument("--no-log",
            dest="buildlog",
            action="store_false",
            default=True,
            help="Do not create a build log. This log contains all files being "
                 "generated, their source files and the module which generated "
                 "the file.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        parser.config.modules.extend(args.modules)
        build_modules = get_modules(parser, repo_options)

        lbuild.environment.simulate = args.simulate
        buildlog = lbuild.buildlog.BuildLog(args.path)
        parser.build_modules(args.path, build_modules, buildlog)

        if args.simulate:
            ostream = []
            for op in buildlog.operations:
                ostream.append(op.local_filename_out())
            return "\n".join(sorted(ostream))
        elif args.buildlog:
            configfilename = args.config
            logfilename = configfilename + ".log"
            with open(logfilename, "wb") as logfile:
                logfile.write(buildlog.to_xml(to_string=True, path=os.getcwd()))

        return ""


class CleanAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("clean",
            help="Remove previously generated files.")
        parser.add_argument("--buildlog",
            dest="buildlog",
            help="Use the given buildlog to identify the files to remove.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        ostream = []
        if args.buildlog is not None:
            with open(args.buildlog, "rb") as logfile:
                buildlog = lbuild.buildlog.BuildLog.from_xml(logfile.read(), path=os.getcwd())
        else:
            build_modules = get_modules(parser, repo_options)

            lbuild.environment.simulate = True
            buildlog = lbuild.buildlog.BuildLog(args.path)
            parser.build_modules(args.path, build_modules, buildlog)

        dirs = set()
        filenames = [op.local_filename_out() for op in buildlog.operations]
        for filename in sorted(filenames):
            ostream.append("Removing " + filename)
            dirs.add(os.path.dirname(filename))
            try:
                os.remove(filename)
            except Exception as e:
                pass

        dirs = sorted(list(dirs), key=lambda d: -d.count("/"))
        for di in dirs:
            try:
                os.removedirs(di)
            except Exception as e:
                pass

        return "\n".join(ostream)


class DependenciesAction(ManipulationActionBase):
    config_required = False

    def register(self, argument_parser):
        parser = argument_parser.add_parser("dependencies",
            help="Generate a grahpviz representation of the module dependencies.")
        parser.add_argument("-m", "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select specific modules.")
        parser.add_argument("-n", "--depth",
            dest="depth",
            type=int,
            default=sys.maxsize,
            help="Only show dependencies up to a specific depth. Only valid if "
                 "specific modules are selected, otherwise all modules are printed "
                 "anyways.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, repo_options):
        available_modules = parser.prepare_repositories(repo_options)

        if len(args.modules) == 0:
            selected_modules = [":**"]
        else:
            selected_modules = args.modules
        selected_modules = parser.find_modules(selected_modules)
        dot_file = lbuild.builder.dependency.graphviz(parser,
                                                      selected_modules,
                                                      args.depth,
                                                      clustered=False)
        return dot_file


def prepare_argument_parser():
    """
    Set up the argument parser for the different commands.

    Return:
    Configured ArgumentParser object.
    """
    argument_parser = argparse.ArgumentParser(
        description='Build source code libraries from modules.')
    argument_parser.add_argument('-r', '--repository',
        metavar="REPO",
        dest='repositories',
        action='append',
        default=[],
        help="Repository file(s) which should be available for the current library. "
             "The loading of repository files from a VCS is only supported through "
             "the library configuration file.")
    argument_parser.add_argument('-c', '--config',
        dest='config',
        default='project.xml',
        help="Project configuration file. "
             "Specifies the required repositories, modules and options "
             "(default: '%(default)s').")
    argument_parser.add_argument('-p', '--path',
        dest='path',
        default='.',
        help="Path in which the library will be generated (default: '%(default)s').")
    argument_parser.add_argument('-D', '--option',
        metavar='OPTION',
        dest='options',
        action='append',
        type=str,
        default=[],
        help="Additional options. Options given here will be merged with options "
             "from the configuration file and will overwrite the configuration "
             "file definitions.")
    argument_parser.add_argument('-v', '--verbose',
        action='count',
        default=0,
        dest='verbose')
    argument_parser.add_argument("--plain",
        dest="plain",
        action="store_true",
        default=False,
        help="Disable styled output, only output plain ASCII.")
    argument_parser.add_argument('--version',
        action='version',
        version='%(prog)s {}'.format(__version__),
        help="Print the lbuild version number and exit.")

    subparsers = argument_parser.add_subparsers(title="Actions",
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


def run(args, system_config=None):
    lbuild.logger.configure_logger(args.verbose)
    lbuild.format.plain = args.plain

    try:
        command = args.execute_action
    except AttributeError:
        raise lbuild.exception.LbuildArgumentException("No command specified")

    fail_silent = not command.__self__.config_required
    config = lbuild.config.ConfigNode.from_file(args.config, fail_silent=fail_silent)
    config.extend_last(system_config)
    return command(args, config)


def main():
    """
    Main entry point of lbuild.
    """
    try:
        argument_parser = prepare_argument_parser()

        commandline_arguments = sys.argv[1:]
        args = argument_parser.parse_args(commandline_arguments)
        lbuild.logger.configure_logger(args.verbose)

        output = run(args, lbuild.config.ConfigNode.from_filesystem())
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
