# Repositories

*lbuild* calls these three functions for any repository file:

- `init(repo)`: provides name, documentation and other global functionality.
- `prepare(repo, options)`: adds all module files for this repository.
- `build(env)` (*optional*): *only* called if at least one module within the
  repository is built. It is meant for actions that must be performed for *any*
  module, like generating a global header file, or adding to the include path.

```python
# You can use everything Python has to offer
import antigravity

def init(repo):
    # You must give your repository a name, and it must be unique within the
    # scope of your project as it is used for namespacing all modules
    repo.name = "name"
    # You can set a repository description here, either as an inline string
    repo.description = "Repository Description"
    # or as a multi-line string
    repo.description = """
Multiline description.

Use whatever markup you want, lbuild treats it all as text.
"""
    # or read it from a separate file altogether
    repo.description = FileReader("module.md")

    # lbuild displays the descriptions as-is, without any modification, however,
    # you can set a custom format handler to change this for your repo.
    # NOTE: Custom format handlers are applied to all modules and options.
    def format_description(node, description):
        # in modm there's unit test metadata in HTML comments, let's remove them
        description = re.sub(r"\n?<!--.*?-->\n?", "", description, flags=re.S)
        # forward this to the default formatter
        return node.format_description(node, description)
    repo.format_description = format_description

    # You can also format the short descriptions for the discover views
    def format_short_description(node, description):
        # Remove the leading # from the Markdown headers
        return node.format_short_description(node, description.replace("#", ""))
    repo.format_short_description = format_short_description

    # Add ignore patterns for all repository modules
    # ignore patterns follow fnmatch rules
    repo.add_ignore_patterns("*/*.lb", "*/board.xml")

    # Add Jinja2 filters for all repository modules
    # NOTE: the filter is namespaced with the repository! {{ "A" | repo.number }} -> 65
    repo.add_filter("repo.number", lambda char: ord(char))

    # Add an alias for a internal configuration
    # NOTE: the configuration is namespaced with the repository! <extends>repo:config</extends>
    repo.add_configuration(Configuration(name="config",
                                         description="Special Config",
                                         path="path/to/config.xml")
    # You can also add configuration versions
    repo.add_configuration(Configuration(name="config2",
                                         description="Versioned Config",
                                         path={"v1": "path/to/config_v1.xml",
                                               "v2": "path/to/config_v2.xml"})

    # See Options for more option types
    repo.add_option(StringOption(name="option", default="value"))


def prepare(repo, options):
    # Access repository options via the `options` resolver
    if options["repo:option"] == "value":
        # Adds module files directly, or via globbing, all paths relative to this file
        repo.add_modules("folder/module.lb", repo.glob("*/*/module.lb"))
    # Searches recursively starting at basepath, adding any file that
    # fnmatch(`modulefile`), while ignoring fnmatch(`ignore`) patterns
    repo.add_modules_recursive(basepath=".", modulefile="*.lb", ignore="*/ignore/patterns/*")


# The build step is optional
def build(env):
    # Add the generated src/ folder to the header search path collector
    env.collect("::include_path", "src/")
    # See module.build(env) for complete feature description.
```
