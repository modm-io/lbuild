#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import argparse
import pkgutil
import logging.config
from lxml import etree

import lbuild.environment
import lbuild.repository

logger = logging.getLogger(__name__)


REPO_FILENAME = 'repo.lb' 

class ParserException(Exception):
    None


def parse_configfile(filename):
    """Parse the project configuration file.

    This file contains information about which modules should be included
    and how they are configured.
    """
    try:
        logger.debug("Parse library configuration '%s'" % filename)
        xmlroot = etree.parse(filename)
        
        xmlschema = etree.fromstring(pkgutil.get_data('lbuild', 'resources/library.xsd'))
        
        schema = etree.XMLSchema(xmlschema)
        schema.assertValid(xmlroot)

        xmltree = xmlroot.getroot()
    except OSError as e:
        raise ParserException(e)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise ParserException("ERROR while parsing xml-file '%s': %s" % (filename, e))

    modules = []
    for modulesNode in xmltree.findall('modules'):
        for moduleNode in modulesNode.findall('module'):
            modulename = moduleNode.text
            logger.debug("- require module '%s'" % modulename)
            modules.append(modulename)

    systemOptions = {}
    for e in xmltree.find('options').findall('option'):
        systemOptions[e.attrib['name']] = e.attrib['value']
    
    config = {
        'system': systemOptions,
        'modules': modules,
    }
    return config


def search_repositories(repositories):
    repos = []
    for repo in repositories:
        repofile = os.path.join(repo, REPO_FILENAME)
        if os.path.isfile(repofile):
            logger.debug("Search in repository '%s'" % repo)
            repository = parse_repository(repofile)
            
            # look for modules inside the repository
            for path, _, files in os.walk(repo):
                if 'module.lb' in files:
                    repository.appendModule(os.path.join(path, 'module.lb'))
            
            repos.append(repository)
        else:
            logger.debug("No repository configuration found '%s'" % repofile)
    return repos


def parse_repository(filename):
    repo = lbuild.repository.Repository()
    
    try:
        with open(filename) as f:
            code = compile(f.read(), filename, 'exec')
            local = {}
            exec(code, local)
            
            prepare_function = local.get('prepare')
            if prepare_function is None:
                raise ParserException("No prepare() function found!")
            
            prepare_function(repo)
    except Exception as e:
        raise ParserException("Invalid repository configuration in '%s': %s" % (filename, e))
    
    return repo


def parse_modules(repositories, config):
    modules = {}
    for repo in repositories:
        for modulefile in repo.getModules():
            try:
                with open(modulefile) as f:
                    logger.debug("Parse modulefile '%s'" % modulefile)
                    code = compile(f.read(), modulefile, 'exec')
        
                    local = {}
                    exec(code, local)
                    
                    module = {}
                    
                    module['modulepath'] = os.path.dirname(modulefile)
                    module['environment'] = lbuild.environment.Environment(module['modulepath'], config['__outpath'])
                    
                    configure_function = local.get('configure')
                    if configure_function is None:
                        raise ParserException("No configure() function found!")
                    
                    # Execute configure() function from module
                    configuration = configure_function(module['environment'])
                    
                    try:
                        module['name'] = configuration['name']
                        module['depends'] = configuration['depends']
                    except TypeError as e:
                        raise ParserException("configure() function must return a dict with 'name' and 'depends'")
                    
                    module['build'] = local['build']
        
                    # Append to the list of available modules
                    modules[module['name']] = module
                    
                    logger.info("Found module '%s'" % module['name'])
            except Exception as e:
                raise ParserException("Invalid module configuration in '%s': %s" % (modulefile, e))
    return modules


def resolve_dependencies(config, modules):
    """Resolve dependencies by adding missing modules"""
    current = config['modules']
    while 1:
        additional = []
        for m in current:
            for d in modules[m]['depends']:
                if d not in config['modules'] and d not in additional:
                    additional.append(d)
        if not additional:
            # Abort if no new dependencies are being found
            break
        config['modules'].extend(additional)
        current = additional
        additional = []


def main():
    parser = argparse.ArgumentParser(description='Build libraries from source code repositories')
    parser.add_argument('-r', '--repository',
        dest='repositories',
        required=True,
        action='append',
        help='Folder in which modules are located')
    parser.add_argument('-p', '--project',
        dest='project',
        required=True,
        help='Project/library configuration file')
    parser.add_argument('-o', '--__outpath',
        dest='__outpath',
        default='.',
        help='Output path to which the  library will be generated')
    parser.add_argument('-v', '--verbose',
        action='count',
        default = 0,
        dest='verbose')

    args = parser.parse_args()
    
    logging.config.dictConfig({
        'version': 1,              
        'disable_existing_loggers': False,
        'formatters': {
            'full': {
                #'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                'format': '[%(levelname)s] %(name)s: %(message)s'
            },
            'simple': {
                'format': '%(message)s'
            },
        },
        'handlers': {
            'default': {
                'class':'logging.StreamHandler',
                'formatter': 'full',
            },
        },
        'loggers': {
            '': {                  
                'handlers': ['default'],        
                'level': 'DEBUG' if args.verbose > 1 else ('INFO' if args.verbose == 1 else 'WARNING'),
                'propagate': True  
            }
        }
    })
    
    try:
        config = parse_configfile(args.project)
        config['__outpath'] = args.__outpath
    
        repositories = search_repositories(args.repositories)
        modules = parse_modules(repositories, config)
    
        resolve_dependencies(config, modules)
    
        # Build the project
        for m in config['modules']:
            module = modules[m]
            build = module['build']
            
            logger.info("Build module '%s'" % module['name'])
            build(module['environment'], config)
    except ParserException as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)