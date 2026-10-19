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

The complete lbuild command line interface is available with `lbuild -h`.
