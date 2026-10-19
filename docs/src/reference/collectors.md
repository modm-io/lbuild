# Collectors

The post-build step has access to the build log containing the list of modules
that were built and what files they generated.
However, these modules also need to pass additional data to the post-build steps,
so that this information can be computed locally.

*lbuild* allows each module to declare what metadata it wants using a collector,
which is given a name, description and optional limitations depending on type.
In the build step, each module may add values to this collector, which the
post-build steps then can access.

```python
def prepare(module, options):
    # Add a collector to module
    collector = Collector(...)
    module.add_collector(collector)

def build(env):
    exists = env.has_collector(":module:collector")
    # Add values to this collector
    env.collect(":module:collector", "value1", "value2", "value3")

def post_build(env):
    # Get all unique values from all operations
    unique_values = env.collector_values(":module:collector")
    # get all values from all operations, even duplicates!
    all_values = env.collector_values(":module:collector", unique=False)
    # Raises an exception if the collector doesn't exist, for example because
    # its module is not built. A default value is returned instead, if the
    # collector doesn't exist or has no values.
    values = env.collector_values(":module:collector", default=[])
```

Note that the ordering of values is preserved only relative to the order they
were added within a module and only if accessing them non-uniquely!
The above example will preserve the order of `value1`, `value2` and `value3`,
only if the values are accessed not uniquely and only relative to each other.

When you add values to a collector, the current operation is recorded, consisting
out of the current module, but you may also explicitly set this to a set of
file operations:

```python
def build(env):
    operation = env.copy("file.hpp")
    # Add values to this collector for the file operation
    env.collect(":module:collector", "values", operations=operation)

    # The return value from a file operation is actually a set of operations
    operations = env.copy("folder1/")
    # So you can extend this set for multiple file operations
    operations |= env.copy("folder2/")
    # And then filter this set of operations
    operations = filter(lambda op: op.filename.endswith(".txt"), operations)
    # Only add this metadata to .txt files
    env.collect(":module:collector", "txt-file-values", operations=operations)

    # A file operation object has these properties:
    operation.module # full module name, this is always available
    operation.repository # repository name, always available
    operation.has_filename # Some operations are specific to files
    operation.filename # The generated filename relative to outpath

def post_build(env):
    # You can use these operation properties to filter the collector values
    txt_filter = lambda op: op.repository == "repo" and op.filename.endswith(".txt")
    unique_txt_values = env.collector_values(":module:collector", filterfunc=txt_filter)
    # May contain duplicate values!
    all_txt_values = env.collector_values(":module:collector", filterfunc=txt_filter, unique=False)
```

If you have very special requirements for the ordering values (for example
when collecting compile flags), consider iterating over the collectors items
manually, and possibly de-duplicating and reordering the values yourself.

```python
def post_build(env):
    # Get the collector, raises an exception if the collector does not exist!
    if env.has_collector(":module:collector"):
        collector = env.collector(":module:collector")
        for operation, values in collector.items():
            # values is a list and may contain duplicates
            print(operation.module, values)
            if operation.has_filename: # not all operations have filenames!
                print(operation.filename)
```

Note that collector values that were added by a module without explicit
operations do not have filename, only module names!

Collectors are implemented using the same type-safe mechanisms as
[Options](options.md), the only differences are the lack of dependency handlers
and default values, since you can add default values in the modules build step.

You may add collector values via the project configuration. However, since these
collector values cannot be overwritten by inheriting configurations use this with care.

```xml
<library>
  <collectors>
    <collect name="repo:collector_name">value</collect>
    <collect name="repo:collector_name">value2</collect>
  </collectors>
</library>
```

You can discover all the available collectors in your repository using
`lbuild discover --developer`.


## CallableCollector

This collector allows you to collect callable objects, that the post-build step
can execute. This can be useful for providing specializations to the post-build
module without it needing to know how they work.

```python
collector = CallableCollector(name="collector-name",
                              description="callable")
```


## StringCollector

See [StringOption](options.md#stringoption) for documentation.

```python
collector = StringCollector(name="collector-name",
                            description="string",
                            validate=validate_function)
```


## PathCollector

See [PathOption](options.md#pathoption) for documentation.

```python
collector = PathCollector(name="collector-name",
                          description="path",
                          empty_ok=False,
                          absolute=False)
```


## BooleanCollector

See [BooleanOption](options.md#booleanoption) for documentation.

```python
collector = BooleanCollector(name="collector-name",
                             description="boolean")
```


## NumericCollector

See [NumericOption](options.md#numericoption) for documentation.

```python
collector = NumericCollector(name="collector-name",
                             description="numeric",
                             minimum=0,
                             maximum=100)
```


## EnumerationCollector

See [EnumerationOption](options.md#enumerationoption) for documentation.

```python
collector = EnumerationCollector(name="collector-name",
                                 description="enumeration",
                                 enumeration=enumeration)
```
