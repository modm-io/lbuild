# Options

*lbuild* options are mappings from strings to Python objects.
Each option must have a unique name within their parent repository or module.
If you do not provide a default value, the option is marked as **REQUIRED** and
the project cannot be built without it.

```python
def prepare(module, options):
    # Add option to module
    option = Option(...)
    module.add_option(option)

def build(env):
    # Check if options exist
    exists = env.has_option(":module:option")
    # Access option value or use default if option doesn't exist
    value = env.get(":module:option", default="value")
    # Access option values, this may raise an exception if option doesn't exist
    value = env[":module:option"]
```

If your option requires a unique set of input values, you can tell *lbuild* to 
wrap the option into a set using `module.add_set_option()`:

```python
def prepare(module, options):
    # Add an option, but allow a set of unique values as input and output
    module.add_set_option(option)
    # You can also give the set a default value as a list or a comma-separated string
    module.add_set_option(option, default=["value", 1])

def build(env):
    # a unique set of option values is returned here
    for value in env[":module:option"]:
        print(value)
```

Option sets are declared as comma-separated strings, so that inheriting
configurations or passing option values via CLI can overwrite these sets.
A `StringOption` cannot be wrapped into a set for this reasons, however, it's
easy to split your string value in Python exactly how you want.

```xml
<!-- All comma separated values are validated by the option -->
<option name=":module:set-option">value, 1, obj</option>
```

If you want to preserve duplicates to count the number of inputs, use a list
option `module.add_list_option()`:

```python
def prepare(module, options):
    # Add an option, but allow a list of values as input and output
    module.add_list_option(option)

def build(env):
    # a list of option values is returned here
    value_count = env[":module:option"].count("value")
```

Options can have a dependency handler which is called when the project
configuration is merged into the module options. It will give you the chosen
input value and you can return a number of module dependencies.

```python
def add_option_dependencies(value):
    if special_condition(value):
        # return single dependency
        return "repo:module"
    if other_special_condition(value):
        # return multiple dependencies
        return [":module1", ":module2"]
    # No additional dependencies
    return None
```


## StringOption

This is the most generic option, allowing to input any string.
You may, however, provide your own validator that may raise a `ValueError`
if the input string does not match your expectations.
You may also pass a transformation function to convert the option value.
The string is passed unmodified from the configuration to the module and the
dependency handler.

```python
def validate_string(string):
    if "please" not in string:
        raise ValueError("Input does not contain the magic word!")

def transform_string(string):
    return string.lower()

option = StringOption(name="option-name",
                      description="inline", # or FileReader("file.md")
                      default="default string",
                      validate=validate_string,
                      transform=transform_string,
                      dependencies=add_option_dependencies)
```


## PathOption

This option operates on strings, but additionally validates them to be
syntactically valid paths, so the filesystem accepts these strings
as valid arguments to path operations. This option does not check if the path
exists, or if it can be created, just if the string is properly formatted.

Since an empty string is not a valid path, but it can be useful to allow an
empty string as an input value to encode a special case (like a "disable" value),
you may set `empty_ok=True` to tell the path validation to ignore empty strings.

By default, the path input is not modified and must be correctly interpreted in
the context of the module that uses it (usually relocated to the output path).
However, if you want to input an existing path you should set `absolute=True`,
so that *lbuild* can relocate the *relative path* declared in the config files
to an absolute path, which is indepented of the CWD.
This is particularly useful if you declare paths in config files that are not
located at the project root, like options inherited from multiple `lbuild.xml`.

```python
option = PathOption(name="option-name",
                    description="path",
                    default="path/to/folder/or/file",
                    empty_ok=False, # is an empty path considered valid?
                    absolute=False, # is the path relative to the config file?
                    validate=validate_path,
                    dependencies=add_option_dependencies)
```


## BooleanOption

This option maps strings from `true`, `yes`, `1`, `enable`, `enabled` to
`bool(True)` and `false`, `no`, `0`, `disable`, `disabled` to `bool(False)`. You can extend this list with a
custom transform handler. The dependency handler is passed this `bool` value.

```python
def transform_boolean(string):
    if string == 'y': return True;
    if string == 'n': return False;
    return string # hand over to built-in conversion

option = BooleanOption(name="option-name",
                       description="boolean",
                       default=True,
                       transform=transform_boolean,
                       dependencies=add_option_dependencies)
```


## NumericOption

This option allows a number from [-Inf, +Inf]. You can limit this to the
range [minimum, maximum].
The values can be specified directly as numeric value or as a string, which is
interpreted using the `eval()` function, so that you can describe values as more
intuitive formulas when necessary.
You can also suffix numbers with the SI multipliers `K`, `M`, `G`, `T`, `Ki`,
`Mi`, `Gi`, and `Ti` to simplify formulas even further.
Note that you should use strings to specify precise floating point values such
as "1/3". The validation and dependency handlers are passed a numeric value.

```python
option = NumericOption(name="option-name",
                       description="numeric",
                       minimum=0,
                       maximum="5Mi*2",
                       default="1K",
                       validate=validate_number,
                       dependencies=add_option_dependencies)
```


## EnumerationOption

This option maps a string to any generic Python object.
You can provide a list, set, tuple or range, the only limitation is that
the objects must be convertible to a string for unique identification.
If this is not possible, you can provide a dictionary with a manual mapping
from string to object, or a Python `enum.Enum` class, which maps the member names
to their values. The dependency handler is passed the string value.

```python
option = EnumerationOption(name="option-name",
                           description="enumeration",
                           # must be implicitly convertible to string!
                           enumeration=["value", 1, obj],
                           # or use a dictionary explicitly
                           enumeration={"value": "value", "1": 1, "obj": obj},
                           # or use an enum.Enum class
                           enumeration=MyEnum,
                           default="1",
                           dependencies=add_option_dependencies)
```
