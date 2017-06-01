#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import sys
import argparse
import textwrap
import traceback

import lbuild.parser
import lbuild.logger
import lbuild.module
import lbuild.vcs.common


def get_modules(parser, repo_options, config_options, selected_module_names=None):
    modules = parser.prepare_repositories(repo_options)

    if selected_module_names is None:
        selected_module_names = [":**"]

    selected_modules = lbuild.module.resolve_modules(modules, selected_module_names)
    build_modules = parser.resolve_dependencies(modules, selected_modules)
    module_options = parser.merge_module_options(build_modules, config_options)

    return build_modules, module_options

def is_repository_option(option_name):
    parts = option_name.split(":")
    if len(parts) < 2:
        raise lbuild.exception.BlobOptionFormatException(option_name)
    elif len(parts) == 2:
        return True
    else:
        return False


class InitAction:
    def register(self, argument_parser):
        parser = argument_parser.add_parser("init",
            help="Load remote repositories into the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    def perform(self, args, config):
        lbuild.vcs.common.initialize(config)


class UpdateAction:
    def register(self, argument_parser):
        parser = argument_parser.add_parser("update",
            help="Update the content of remote repositories in the cache folder.")
        parser.set_defaults(execute_action=self.perform)

    def perform(self, args, config):
        lbuild.vcs.common.update(config)


class ManipulationActionBase:
    """
    Base class for actions that interact directly with the parser repositories.
    """
    def prepare_repositories(self, args, config):
        parser = lbuild.parser.Parser()
        parser.load_repositories(config, args.repositories)

        commandline_options = config.format_commandline_options(args.options)
        repo_options = parser.merge_repository_options(config.options, commandline_options)

        return self.perform(args, parser, config, repo_options)


class DiscoverRepositoryAction(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-repository",
            aliases=['repo'],
            help="Display the repository options of all selected repositories.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        ostream = []
        for option in sorted(list(repo_options.values())):
            ostream.append(option.format())
        return "\n".join(ostream)


class DiscoverModulesActions(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-modules",
            aliases=['modules'],
            help="Inspect all available modules with the given repository options. "
                 "All repository options must be defined.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        ostream = []
        modules = parser.prepare_repositories(repo_options)
        for module in sorted(list(modules.values())):
            ostream.append(str(module))
        return "\n".join(ostream)

class DependenciesAction(ManipulationActionBase):
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

    def perform(self, args, parser, config, repo_options):
        available_modules = parser.prepare_repositories(repo_options)

        if len(args.modules) == 0:
            selected_modules = [":**"]
        else:
            selected_modules = args.modules
        selected_modules = lbuild.module.resolve_modules(available_modules,
                                                         selected_modules)
        dot_file = lbuild.builder.dependency.graphviz(available_modules,
                                                      selected_modules,
                                                      args.depth,
                                                      clustered=False)
        return dot_file


class DiscoverModuleOptionsAction(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-module-options",
            aliases=['options'],
            help="Inspect the module options of one or more modules (if specified "
                 "through the module option(s)) or all available modules (if no "
                 "module is specified).")
        parser.add_argument("-m", "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        if len(args.modules) == 0 and len(config.selected_modules) == 0:
            config.selected_modules.extend([":**"])
        else:
            config.selected_modules.extend(args.modules)
        _, options = get_modules(parser, repo_options, config.options, config.selected_modules)

        ostream = []
        for option in sorted(list(options.values())):
            ostream.append(option.format())

            if option.short_description:
                ostream.append("")
                ostream.append(textwrap.indent(option.short_description, "  "))
                ostream.append("")
        return "\n".join(ostream)


class DiscoverOptionAction(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-option",
            aliases=['option'],
            help="Print the description and values of one option.")
        parser.add_argument("-o", "--option-name",
            dest="option_name",
            required=True,
            help="Select a specific module")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        option_name = args.option_name
        if is_repository_option(option_name):
            option = lbuild.module.find_module(repo_options, option_name)
        else:
            _, options = get_modules(parser, repo_options, config.options)
            option = lbuild.module.find_module(options, option_name)

        return option.factsheet() + "\n"


class DiscoverOptionValuesAction(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("discover-option-values",
            aliases=['option-values'],
            help="Print the values of one option.")
        parser.add_argument("-o", "--option-name",
            dest="option_name",
            required=True,
            help="Select a specific module")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        option_name = args.option_name
        if is_repository_option(option_name):
            option = lbuild.module.find_module(repo_options, option_name)
        else:
            _, options = get_modules(parser, repo_options, config.options)
            option = lbuild.module.find_module(options, option_name)

        ostream = []
        for value in lbuild.utils.listify(option.values):
            ostream.append(str(value))
        return "\n".join(ostream)


class BuildAction(ManipulationActionBase):
    def register(self, argument_parser):
        parser = argument_parser.add_parser("build",
            help="Generate the library source code blob with the given options.")
        parser.add_argument("-m", "--module",
            dest="modules",
            type=str,
            action="append",
            default=[],
            help="Select a specific module.")
        parser.add_argument("--no-log",
            dest="buildlog",
            action="store_false",
            default=True,
            help="Do not create a build log. This log contains all files being "
                 "generated, their source files and the module which generated "
                 "the file.")
        parser.set_defaults(execute_action=self.prepare_repositories)

    def perform(self, args, parser, config, repo_options):
        log = lbuild.buildlog.BuildLog()

        config.selected_modules.extend(args.modules)
        build_modules, module_options = get_modules(parser, repo_options, config.options, config.selected_modules)
        parser.build_modules(args.path, build_modules, repo_options, module_options, log)

        if args.buildlog:
            configfilename = args.config
            logfilename = configfilename + ".log"
            with open(logfilename, "wb") as logfile:
                logfile.write(log.to_xml(to_string=True))
        return ""


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
        help="Project/library configuration file. "
             "Specifies the used repositories, modules and options "
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
             "file definitions. "
             "Use a single colon to specify repository options and multiple "
             "colons to specify (sub)module options.")
    argument_parser.add_argument('-v', '--verbose',
        action='count',
        default=0,
        dest='verbose')

    subparsers = argument_parser.add_subparsers(title="Actions",
        dest="action")

    actions = [
        InitAction(),
        UpdateAction(),
        DiscoverRepositoryAction(),
        DiscoverModulesActions(),
        DependenciesAction(),
        DiscoverModuleOptionsAction(),
        DiscoverOptionAction(),
        DiscoverOptionValuesAction(),
        BuildAction(),
    ]
    for action in actions:
        action.register(subparsers)

    return argument_parser


def run(args):
    lbuild.logger.configure_logger(args.verbose)

    config = lbuild.config.Configuration.parse_configuration(args.config)
    return args.execute_action(args, config)


def main():
    """
    Main entry point of lbuild.
    """
    try:
        argument_parser = prepare_argument_parser()

        commandline_arguments = sys.argv[1:]
        args = argument_parser.parse_args(commandline_arguments)

        output = run(args)
        print(output)
    except lbuild.exception.BlobAggregateException as aggregate:
        for error in aggregate.exceptions:
            sys.stderr.write('\nERROR: %s\n' % error)
        sys.exit(2)
    except lbuild.exception.BlobArgumentException as error:
        argument_parser.print_help()
        print(error)
        sys.exit(2)
    except lbuild.exception.BlobTemplateException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        traceback.print_exc()
        sys.exit(3)
    except lbuild.exception.BlobException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        if args.verbose >= 2:
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
