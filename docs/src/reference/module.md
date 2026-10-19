# Modules

*lbuild* calls these five functions for any module file:

- `init(module)`: provides module name, parent and documentation.
- `prepare(module, options)`: enables modules, adds options and submodules by
  taking the repository options into consideration.
- `validate(env)` (*optional*): validate your inputs before building anything.
- `build(env)`: generate your library and add metadata to build log.
- `post_build(env)` (*optional*): access the build log after the build
  step completed.

Module files are provided with these additional global classes:

- `Module`: Base class for generated modules.
- `ValidateException`: Exception to be raised when the `validate(env)` step fails.

Accessing an option or query of another module via `env[...]` or `env.query(...)`
logs a warning if your module does not depend on that module, since it may not
be built. Use `lbuild validate --strict` to turn these warnings into errors.

Note that in contrast to a repository, modules must return a boolean from the
`prepare(module, options)` function, which indicates that the module is available
for the repository option configuration. This allows for modules to "share" a
name, but have completely different implementations.

The `validate(env)` step is used to validate the input for the build step,
allowing for computations that can fail to raise a `ValidateException("reason")`.
*lbuild* will collect these exceptions for all modules and display them
together before aborting the build. This step is performed before each build,
and you cannot generate any files in this step, only read the repository's state.
You can manually call this step via the `lbuild validate` command.

The `build(env)` step is where the actual file generation happens. Here you can
copy and generate files and folders from Jinja2 templates with the substitutions
of you choice and the configuration of the modules. Each file operation is
appended to a global build log, which you can also explicitly add metadata to.

The `post_build(env)` step is meant for modules that need to generate
files which receive information from all built modules. The typically use-case
here is generating scripts for build systems, which need to know about what
files were generated and all module's metadata.

```python
def init(module):
    # give your module a hierarchical name, the repository name is implicit
    module.name = "repo:name"
    module.name = ":name"      # same as this
    # You can set a module description here
    module.description = "Description"
    module.description = """Multiline"""
    module.description = FileReader("module.md")
    # modules can have their own formatters, works the same as for repositories
    module.format_description = custom_format_description
    module.format_short_description = custom_format_short_description
    # Add Jinja2 filters for this modules and all submodules
    # NOTE: the filter is namespace with the repository! {{ 65 | repo.character }} -> "A"
    module.add_filter("repo.character", lambda number: chr(number))
    # Modules with a higher order are built after all modules with a lower
    # order, see Execution Order. Default is 0.
    module.order = 10000


def prepare(module, options):
    # Access repository options via the `options` resolver
    if options["repo:option"] == "value":
        # Returning False from this step disables this module
        return False

    # modules can depend on other modules
    module.depends("repo:module1", ":module2", ":module3:submodule", ...)

    # You can add more submodules in files
    module.add_submodule("folder/submodule.lb")

    # You can generate more modules here. This is useful if you have a lot of
    # very similar modules (like instances of hardware peripherals) that you
    # don't want to create a module file for each for.
    class Instance(Module):
        def __init__(self, instance):
            self.instance = instance
        def init(self, module):
            module.name = str(self.instance)
        def prepare(self, module, options):
            return True
        def validate(self, env): # optional
            pass
        def build(self, env):
            pass
        def post_build(self, env): # optional
            pass

    # You can statically create and add these submodules
    for index in range(0, 5):
        module.add_submodule(Instance(index))
    # or make the creation dependent on a repository option
    for index in options["repo:instances"]:
        module.add_submodule(Instance(index))

    # See Options for more option types
    module.add_option(StringOption(name="option", description="Option", default="world"))

    def common_operation(args):
        """
        You can share any function with other modules.
        This is useful to not have to duplicate code across module.lb files.
        """
        return args
    # See Queries for more query types
    module.add_query(Query(name="shared_function", function=common_operation))

    # You can collect information from active modules, to use any post_build step
    # See Collectors for more collector types
    module.add_collector(
        PathCollector(name="include_path", description="Global header search paths"))

    # Make this module available
    return True


# store data computed in validate step for build step.
build_data = None
# The validation step is optional
def validate(env):
    # Perform your input validations here
    # Access all options
    repo_option = env["repo:option"]
    defaulted_option = env.get("repo:module:option", default="hello")
    # Use proper logging instead of print() please
    # env.log.warning(...) and env.log.error(...) also available
    env.log.debug("Repo option: '{}'".format(repo_option))

    # You can check if a module is built or if an option exists. Only modules
    # that are built and their options are visible to this check!
    if env.has_option("repo:module:option") or env.has_module("repo:module"):
        env.log.info("Module option: '{}'".format(env["repo:module:option"]))

    # Call shared functions from other modules with arguments
    shared_function = env.query("repo:module:shared_function")
    result = shared_function("argument")
    # Or just precomputed properties without arguments
    data = env.query("repo:module:shared_property")

    # You may also use incomplete queries, see Name Resolution
    env.has_module(":module") # instead of repo:module
    env.has_option("::option") # repo:module:option
    # And use fnmatch queries
    # matches any module starting with `mod` and option starting with `name`.
    env.has_option(":mod*:name*")
    env.has_query("::shared_*")
    env.has_collector("::collector")

    # Raise a ValidateException if something is wrong
    if defaulted_option + repo_option != "hello world":
        raise ValidateException("Options are invalid because ...")

    # If you do heavy computations here for validation, you can store the
    # data in a global variable and reuse this for the build step
    global build_data
    build_data = defaulted_option * 2
```

The `build(env)` and `post_build(env)` steps are described in [Environment](environment.md).
