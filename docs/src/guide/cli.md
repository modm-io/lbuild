# Command Line Interface

Before you can build a project you need to provide a configuration.
*lbuild* aims to make discovery easy from the command line:

```
 $ lbuild --repository ../modm/repo.lb discover
Parser(lbuild)
╰── Repository(modm @ ../modm)   modm: a barebone embedded library generator
    ╰── Option(target) = REQUIRED in [at90can128, at90can32, at90can64, ...
```

This gives you an overview of the repositories and their options. In this case
the `modm:target` repository option is required, so let's check that out:

```
 $ lbuild -r ../modm/repo.lb discover-options
modm:target = REQUIRED in [at90can128, at90can32, at90can64, at90pwm1, at90pwm161, at90pwm2,
                           ... a really long list ...
                           stm32l4s9vit, stm32l4s9zij, stm32l4s9zit, stm32l4s9ziy]

  Meta-HAL target device
```

You can then choose this repository option and discover the available modules
for this specific repository option:

```
 $ lbuild -r ../modm/repo.lb --option modm:target=stm32f407vgt discover
Parser(lbuild)
╰── Repository(modm @ ../modm)   modm: a barebone embedded library generator
    ├── Option(target) = stm32f407vgt in [at90can128, at90can32, at90can64, ...]
    ├── Configuration(modm:disco-f407vg)
    ├── Module(modm:board)   Board Support Packages
    │   ╰── Module(modm:board:disco-f469ni)   STM32F469IDISCOVERY
    ├── Module(modm:build)   Build System Generators
    │   ├── PathOption(build.path) = build/parent-folder in [String]
    │   ├── Option(project.name) = parent-folder in [String]
    │   ╰── Module(modm:build:scons)  SCons Build Script Generator
    │       ├── Option(info.build) = no in [yes, no]
    │       ╰── Option(info.git) = Disabled in [Disabled, Info, Info+Status]
    ├── Module(modm:platform)   Platform HAL
    │   ├── Module(modm:platform:can)   Controller Area Network (CAN)
    │   │   ╰── Module(modm:platform:can:1)   Instance 1
    │   │       ├── Option(buffer.rx) = 32 in [1 .. 32 .. 65534]
    │   │       ╰── Option(buffer.tx) = 32 in [1 .. 32 .. 65534]
    │   ├── Module(modm:platform:core)   ARM Cortex-M Core
    │   │   ├── Option(allocator) = newlib in [block, newlib, tlsf]
    │   │   ├── Option(main_stack_size) = 3072 in [256 .. 3072 .. 65536]
    │   │   ╰── Option(vector_table_location) = rom in [ram, rom]
```

You can now discover all module options in more detail:

```
 $ lbuild -r ../modm/repo.lb -D modm:target=stm32f407vgt discover-options
modm:target = stm32f407vgt in [at90can128, at90can32, at90can64, ...]

  Meta-HAL target device

modm:build:build.path = build/parent-folder in [String]

  Path to the build folder

modm:build:project.name = parent-folder in [String]

  Project name for executable
```

Or check out specific module and option descriptions:

```
 $ lbuild -r ../modm/repo.lb -D modm:target=stm32f407vgt discover -n :build
>> modm:build

# Build System Generators

This parent module defines a common set of functionality that is independent of
the specific build system generator implementation.

>>>> modm:build:project.name  [StringOption]

# Project Name

The project name defaults to the folder name you're calling lbuild from.

Value: parent-folder
Inputs: [String]

>>>> modm:build:build.path  [StringOption]

# Build Path

The build path is defaulted to `build/{modm:build:project.name}`.

Value: build/parent-folder
Inputs: [String]
```

You can also search the descriptions of all repositories, modules and options
with one or more regular expressions:

```
 $ lbuild -r ../modm/repo.lb -D modm:target=stm32f407vgt search "DMA" "I2C"
```


## Global Arguments

These arguments go before the command:

- `-r`, `--repository REPO`: Add a repository file. Remote repositories are only
  supported via the [configuration file](configuration.md#remote-repositories).
- `-c`, `--config CONFIG`: Project configuration file (default: `project.xml`).
- `-C`, `--cwd CWD`: Current working directory (default: `.`).
- `-p`, `--path PATH`: Output path in which the library is generated
  (default: CWD).
- `-D`, `--option OPTION`: Set an option as `name=value`. Overwrites the
  configuration file.
- `--collect COLLECTOR`: Add a collector value as `name=value`.
- `-v`, `--verbose`: Increase the log level, can be repeated (`-vvv`).
- `--plain`: Disable styled output, only output plain ASCII.


## Commands

- `discover [NAME ...]`: Render the repository tree, or the descriptions of the
  named nodes.
    + `-n`, `--name NAME`: Same as passing `NAME` as positional argument.
    + `-t`, `--tree`: Render the subtree of the named nodes instead.
    + `--values`: Display the possible values of the named options.
    + `--developer`: Show developer nodes like queries and collectors.
- `discover-options`: Display all option names, values, inputs and short
  descriptions. Use `-n NAME` to select specific options.
- `search QUERY ...`: Search all descriptions for regular expressions and
  render the matching nodes and lines.
- `validate`: Validate the configuration and run the `validate(env)` steps.
  This also shows warnings for deprecated APIs.
    + `-m`, `--module MODULE`: Only validate specific modules.
    + `--strict`: Treat logging warnings as errors.
- `build`: Generate the library.
    + `-m`, `--module MODULE`: Only build specific modules.
    + `--simulate`: Build, but do not write any files. Prints out all generated
      file names.
    + `--symlink`: Symlink copied files instead of copying them. Be careful
      editing them, since you are editing the files in the repository!
    + `--no-log`: Do not write the build log next to the configuration file
      (`project.xml.log`).
- `clean`: Remove all files listed in the build log of the previous build. If
  there is no build log, the files of a simulated build are removed.
    + `--buildlog BUILDLOG`: Use a specific build log.
- `init`: Clone the remote repositories into the cache folder.
- `update`: Update the remote repositories in the cache folder.
- `dependencies`: Generate a Graphviz representation of the module dependencies.
    + `-m`, `--module MODULE`: Only show specific modules.
    + `-n`, `--depth DEPTH`: Only show dependencies up to a specific depth.

The complete lbuild command line interface is available with `lbuild -h` and
`lbuild COMMAND -h`.
