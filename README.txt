
Introduction
============

'blob' is a library builder used to generate a blob of files from a source code
repository.


Operation
---------

blob gets the path to a number of repository files and a configuration file.
The repository files define what modules and global options are available and
where the modules are located.

Repository -> Modules -> module:init() -> Module Name

Configuration options + repository options -> module:prepare() -> Module availability, options and dependencies

required modules -> needed modules

Configuration module options + configuration options + needed module -> Environment

needed module + environment -> module:build()



repository:module:option
repository:option
:option
:module:option
::option 