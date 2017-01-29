
.. image:: https://travis-ci.org/dergraaf/library-builder.svg?branch=develop
    :target: https://travis-ci.org/dergraaf/library-builder

Introduction
============

*lbuild* is a library builder used to generate a blob of files from a source
code repository.


Definition of Terms
-------------------

Repository:
  Collection of modules. A repository contains a number of options which are
  used to select which module can be build.

Module:
  When a module is selected and build it copies a number of files to a
  specified output location. It is also possible to use the Jinja2 template
  engine to create new files.

  A module can define its own options used during the build of the module. It
  can also access the options of other modules it depends upon and the
  repository options.

Repository file:
  Python script used to declare the name of the repository, the location of
  the module files within the repository and repository options.

  Must declare the following functions::

    def init(repo):
        ....
    def prepare(repo, options):
        ...

Module file:
  Python script defining a module. A module gets the repository options to
  select whether it can be build with selection of options and which other
  modules are needed.

  Additional options can be defined within the module file. These options are
  available later during the build of the module.

  Must declare the following functions::

    def init(module):
        ...
    def prepare(module, options):
        ...
    def build(env):
        ...

Options:
  There are two kind of options: repository and module options. The repository
  options use the following naming schema::

      repository:option

  Module options use an additional field for the module name::

      repository:module:option

  The repository and module name can be empty. In this case the current
  repository/module name is used.

Configuration file:
  XML file used to define repository/module options and to select which
  modules should be build.

  Defining options in the configuration file follow the same naming schema for
  repository and module options. The only difference being that when the
  repository or module name is left blank all options matching the remaining
  fields are set.

  E.g. defining a value for ``abc::xyz`` will set the given value for all modules
  in the ``abc`` repository which define an option with the name ``xyz``.


API Overview
------------

Repository description ('repo.lb')::

	def init(repo):
		repo.set_name("..")

		repo.add_option(StringOption(name="..", description=".."))

	def prepare(repo, options):
		repo.add_modules(repo.glob("*/*.lb"))
		repo.add_modules("..")

		repo.find_modules


Module description ('module.lb')::

	def init(module):
		module.set_name("..")
		module.set_description("..")

		module.add_option(StringOption(name, description, default))

	def prepare(module, options):
		option_value = options[".."]

		module.depends([".."])

	def build(env):
		env.copy(src, dest, ignore=env.ignore_files("main.*"))
		env.template(src, dest, substitutions)

		modulepath  = env.modulepath(local_path)
		output_path = env.output(local_path)

		option_value = env[".."]

Project configuration ('project.xml')::

	<library>
	  <options>
		<option name=".." value=".." />
		...
	  </options>
	  <modules>
		<module>..</module>
		...
	  </modules>
	</library>


Operation
---------

*lbuild* gets the path to a number of repository files and a configuration file.
The repository files define what modules and global options are available and
where the modules are located.

The functions in the python files are called in the following order::

  for all repositories
     repository:prepare()

  Consolidate repository options

  for all modules
    module:init()

  Consolidate module options

  for all modules
    module:prepare()

  Use available modules to resolve dependencies between modules

  for all modules selected in configuration file or through dependency
    module:build()
