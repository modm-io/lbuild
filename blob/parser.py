#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the blob project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import argparse
import pkgutil
import logging.config
from lxml import etree

from . import exception
from . import module
from . import environment
from . import repository

logger = logging.getLogger('blob.parser')

class Parser:
    
    def __init__(self):
        self.repositories = []
        self.modules = {}
    
    def parse_repository(self, repofile):
        repo = repository.Repository(os.path.dirname(repofile))
        try:
            with open(repofile) as f:
                code = compile(f.read(), repofile, 'exec')
                local = {}
                exec(code, local)
                
                prepare = local.get('prepare')
                if prepare is None:
                    raise exception.BlobException("No prepare() function found!")
                
                # Execution prepare() function. In this function modules and
                # options are added. 
                prepare(repo)
                
                if repo.name is None:
                    raise exception.BlobException("The prepare(repo) function must set a repo name! Please use the set_name() method.")
        except Exception as e:
            raise exception.BlobException("Invalid repository configuration file '%s': %s" % (repofile, e))
        
        self.repositories.append(repo)
        return repo
    
    def parse_modules(self):
        """Parse the module files of all repositories."""
        for repo in self.repositories:
            for modulefile, m in repo.modules.items():
                # Parse all modules which are not yet updated
                if m is None:
                    m = self.parse_module(repo, modulefile)
                    repo.modules[modulefile] = m
                    
                self.modules["%s:%s" % (repo.name, m.name)] = m
    
    def parse_module(self, repo, modulefile):
        """
        Parse a specific module file.
        
        Returns:
            Module() module definition object.
        """
        try:
            with open(modulefile) as f:
                logger.debug("Parse modulefile '%s'" % modulefile)
                code = compile(f.read(), modulefile, 'exec')
        
                local = {}
                exec(code, local)
                
                m = module.Module(repo, modulefile, os.path.dirname(modulefile))
                
                #module['modulepath'] = 
                #module['environment'] = environment.Environment(module['modulepath'], config['__outpath'])
                
                for functionname in ['init', 'prepare', 'build']:
                    f = local.get(functionname)
                    if f is None:
                        raise exception.BlobException("No function '%s' found!" % functionname)
                    m.functions[functionname] = f
                
                # Execute init() function from module
                m.functions['init'](m)
                
                if m.name is None:
                    raise exception.BlobException("The init(module) function must set a module name! Please use the set_name() method.")
                  
                logger.info("Found module '%s'" % m.name)
                
                return m
        except Exception as e:
            raise exception.BlobException("While parsing '%s': %s" % (modulefile, e))
    
    def parse_configuration(self, configfile):
        pass

def parse_configfile(filename):
    """Parse the project configuration file.

    This file contains information about which modules should be included
    and how they are configured.
    """
    try:
        logger.debug("Parse library configuration '%s'" % filename)
        xmlroot = etree.parse(filename)
        
        xmlschema = etree.fromstring(pkgutil.get_data('blob', 'resources/library.xsd'))
        
        schema = etree.XMLSchema(xmlschema)
        schema.assertValid(xmlroot)

        xmltree = xmlroot.getroot()
    except OSError as e:
        raise exception.BlobException(e)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise exception.BlobException("ERROR while parsing xml-file '%s': %s" % (filename, e))

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
    except exception.BlobException as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)