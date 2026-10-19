# lbuild: generic, modular code generation in Python 3

The Library Builder (pronounced *lbuild*) is a BSD licensed [Python 3 tool][python]
for describing repositories containing modules which can copy or generate a set
of files based on the user provided data and options.

*lbuild* allows splitting up complex code generation projects into smaller
modules with configurable options, and provides for their transparent
discovery, documentation and dependency management.
Each module is written in Python 3 and declares its options and how to generate
its content via the [Jinja2 templating engine][jinja2] or a file/folder copy.

You can [install *lbuild* via PyPi][pypi]: `pip install lbuild`

**The documentation is available at [lbuild.modm.dev][docs].**

Projects using *lbuild*:

- [modm generates a HAL for thousands of embedded devices][modm] using *lbuild*
  and a data-driven code generation pipeline.
- [Taproot: a friendly control library and framework for RoboMaster robots][taproot]
  uses *lbuild*.
- [OUTPOST - Open modUlar sofTware PlatfOrm for SpacecrafT][outpost] uses *lbuild*
  to assemble an execution platform targeted at embedded systems running mission
  critical software.

The dedicated maintainer of *lbuild* is [@salkinium][salkinium].


[docs]: https://lbuild.modm.dev
[modm]: https://modm.dev/how-modm-works
[taproot]: https://github.com/uw-advanced-robotics/taproot
[outpost]: https://github.com/DLR-RY/outpost-core
[jinja2]: https://jinja.palletsprojects.com
[python]: https://www.python.org
[pypi]: https://pypi.org/project/lbuild
[salkinium]: https://github.com/salkinium
