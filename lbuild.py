#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the library-builder project and is released under the
# 3-clause BSD license. See the file `LICENSE` for the full license governing
# this code.

import os
import sys
import argparse
import xml.parsers.expat
import xml.etree.ElementTree as et

import pprint

def copytree(src, dst, symlinks=False, ignore=None):
	import shutil
	
	if not os.path.exists(dst):
		os.makedirs(dst)
	for item in os.listdir(src):
		s = os.path.join(src, item)
		d = os.path.join(dst, item)
		if os.path.isdir(s):
			copytree(s, d, symlinks, ignore)
		else:
			if not os.path.exists(d) or os.stat(src).st_mtime - os.stat(dst).st_mtime > 1:
				shutil.copy2(s, d)

def parse_configfile(filename):
	"""Parse the project configuration file.

	This file contains information about which modules should be included
	and how they are configured.
	"""
	try:
		xmltree = et.parse(filename).getroot()
	except (OSError, xml.parsers.expat.ExpatError, et.ParseError) as e:
		raise Exception("while parsing xml-file '%s': %s" % (filename, e))

	modules = []	
	for e in xmltree.findall('module'):
		modules.append(e.text)

	config = {
		'target': xmltree.find('target').text,
		'modules': modules,
	}
	return config

def find_modules(repositories):
	modulefiles = []
	for repo in repositories:
		for path, directories, files in os.walk(repo):
			if 'module.lb' in files:
				modulefiles.append(os.path.join(path, 'module.lb'))
	return modulefiles

def parse_modules(modulefiles, outpath):
	modules = {}
	for modulefile in modulefiles:
		with open(modulefile) as f:
			code = compile(f.read(), modulefile, 'exec')

			def relocate(path):
				return lambda *p: os.path.join(path, *p)
			
			local = {
				'copytree': copytree,
				'modulepath': relocate(os.path.dirname(modulefile)),
				'outpath': relocate(outpath),
			}
			exec(code, local)

			module = local['configure'](config['target'])
			
			module['build'] = local['build']
			module['modulepath'] = os.path.dirname(modulefile)

			# Append to the list of available modules
			modules[module['name']] = module
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

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Build Latex files')
	parser.add_argument('-r', '--repository',
		dest='repositories',
		required=True,
		action='append',
		help='Folder in which modules are located')
	parser.add_argument('-p', '--project',
		dest='project',
		required=True,
		help='Project/library configuration file')
	parser.add_argument('-o', '--outpath',
		dest='outpath',
		default='.',
		help='Output path to which the  library will be generated')

	args = parser.parse_args()

	config = parse_configfile(args.project)
	config['outpath'] = args.outpath

	modulefiles = find_modules(args.repositories)
	modules = parse_modules(modulefiles, args.outpath)

	resolve_dependencies(config, modules)

	# Build the project
	for m in config['modules']:
		module = modules[m]
		build = module['build']
		build(config)
	
	#print(config['modules'])
	#pprint.pprint(modules)

#libpath = os.path.dirname(os.path.realpath(__file__))

