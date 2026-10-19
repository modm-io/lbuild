# lbuild: generic, modular code generation in Python 3

The Library Builder (pronounced *lbuild*) is a BSD licensed [Python 3 tool][python]
for describing repositories containing modules which can copy or generate a set
of files based on the user provided data and options.

*lbuild* allows splitting up complex code generation projects into smaller
modules with configurable options, and provides for their transparent
discovery, documentation and dependency management.
Each module is written in Python 3 and declares its options and how to generate
its content via the [Jinja2 templating engine][jinja2] or a file/folder copy.

You can [install *lbuild* via PyPi][pypi]: `pip install lbuild`.
See [Installation](guide/installation.md) for details.

Projects using *lbuild*:

- [modm generates a HAL for thousands of embedded devices][modm] using *lbuild*
  and a data-driven code generation pipeline.
- [Taproot: a friendly control library and framework for RoboMaster robots][taproot]
  uses *lbuild*.
- [OUTPOST - Open modUlar sofTware PlatfOrm for SpacecrafT][outpost] uses *lbuild*
  to assemble an execution platform targeted at embedded systems running mission
  critical software.

The dedicated maintainer of *lbuild* is [@salkinium][salkinium].


## Overview

Consider this repository:

```
 $ lbuild discover
Parser(lbuild)
╰── Repository(repo @ ../repo)
    ├── Option(option) = value in [value, special]
    ├── Module(repo:module)
    │   ├── Option(option) = yes in [yes, no]
    │   ├── Module(repo:module:submodule)
    │   │   ╰── Option(option) = REQUIRED in [1, 2, 3, 4, 5]
    │   ╰── Module(repo:module:submodule2)
    ╰── Module(modm:module2)
```

*lbuild* is called by the user with a configuration file which contains the
repositories to scan, the modules to include and the options to configure
them with:

```xml
<library>
  <repositories>
    <repository><path>../repo/repo.lb</path></repository>
  </repositories>
  <options>
    <option name="repo:option">special</option>
    <option name="repo:module:option">3</option>
  </options>
  <modules>
    <module>repo:module</module>
  </modules>
</library>
```

The `repo.lb` file is compiled by *lbuild* and the two functions `init`,
`prepare` are called:

```python
def init(repo):
    repo.name = "repo"
    repo.add_option(EnumerationOption(name="option",
                                      enumeration=["value", "special"],
                                      default="value"))

def prepare(repo, options):
    repo.find_modules_recursive("src")
```

This gives the repository a name and declares a string option. The prepare step
adds all module files in the `src/` folder.

Each `module.lb` file is then compiled by *lbuild*, and the three functions
`init`, `prepare` and `build` are called:

```python
def init(module):
    module.name = ":module"

def prepare(module, options):
    if options["repo:option"] == "special":
        module.add_option(EnumerationOption(name="option", enumeration=[1, 2, 3, 4, 5]))
        return True
    return False

def build(env):
    env.outbasepath = "repo/module"
    env.copy("static.hpp")
    for number in range(env["repo:module:option"]):
        env.template("template.cpp.in", "template_{}.cpp".format(number + 1))
```

The init step sets the module's name and its parent name. The prepare step
then adds a `EnumerationOption` and makes the module available, if the repository option
is set to `"special"`. Finally in the build step, a number of files are generated
based on the option's content.

The files are generated at the call-site of `lbuild build` which would then
look something like this:

```
 $ ls
main.cpp        project.xml
 $ lbuild build
 $ tree
.
├── main.cpp
├── repo
│   ├── module
│   │   ├── static.hpp
│   │   ├── template_1.cpp
│   │   ├── template_2.cpp
│   │   └── template_3.cpp
```

Continue with the [command line interface](guide/cli.md) and the
[configuration file](guide/configuration.md), or dive into the
[reference](reference/files.md) with examples from [the modm repository][modm].


[modm]: https://modm.io/how-modm-works
[taproot]: https://github.com/uw-advanced-robotics/taproot
[outpost]: https://github.com/DLR-RY/outpost-core
[jinja2]: http://jinja.pocoo.org
[python]: https://www.python.org
[pypi]: https://pypi.org/project/lbuild
[salkinium]: https://github.com/salkinium
