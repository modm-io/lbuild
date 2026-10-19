# Aliases

*lbuild* aliases are mappings from one lbuild node to another. They are useful
for gracefully dealing with renaming or moving nodes in your lbuild module tree.
Aliases will print a warning when accessed showing the alias description. Each
alias must have a unique name within their parent repository or module.

Aliases can be used for any type of node that you want forwarded. You can also
add aliases that do not have a destination and will raise an exception with the
alias description. This allows you to remove lbuild nodes while providing
details for a workaround.

```python
def prepare(module, options):
    # Move option in this module
    module.add_option(StringOption(name="option", description="Option"))
    # Forward the old option to the new option
    module.add_alias(Alias(name="option-alias",
                           destination="option",
                           description="Renamed for clarity."))
    # Instead of silently failing, you can provide a detailed description
    # about why the node was removed and what the workaround is.
    module.add_alias(Alias(name="removed-alias",
                           description="Removed. Workaround: ..."))
    # You alias any type to any other node.
    module.add_alias(Alias(name="submodule-alias",
                           destination=":other-module:submodule",
                           description="Removed. Workaround: ..."))

def build(env):
    # Will show a warning (once) that the alias has been moved
    exists = env.has_option(":module:option-alias")
    # Accesses :module:option instead
    value = env[":module:option-alias"]
    # This will raise an exception with the alias description
    value = env[":module:removed-alias"]
    # will check for :other-module:submodule instead
    value = env.has_module(":module:submodule-alias")
```
