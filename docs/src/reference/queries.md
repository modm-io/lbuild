# Queries

It is sometimes necessary to share code and data between *lbuild* modules,
which can be difficult when they are split across files and repositories.
Queries allow you to share functions and computed properties with other modules
using the global name resolution system.

```python
def prepare(module, options):
    # Add queries to module
    query = Query(...)
    module.add_query(query)

def build(env):
    exists = env.has_query(":module:query")
    # Access query value or use default if query doesn't exist
    data = env.query(":module:query", default="value")
```

*Note that queries must be stateless (aka. a pure function), since module build
order is not guaranteed. You must enforce this property yourself.*

You can discover all the available queries in your repository using
`lbuild discover --developer`.


## Query

This wraps any callable object into a query. By default the name is taken from
the object's name, however, you may overwrite this.
Note that when using a lambda function, you must provide a name.
The description is taken from the objects docstring.

```python
def shared_function(args):
    """
    Describe what this query does.

    :param args: what does it need?
    :returns: what does it return?
    """
    return args

query = Query(function=shared_function)
query = Query(name="different_name",
              function=shared_function)
```


## EnvironmentQuery

This query's result is computed only once on demand and then cached.

The data must be returned from a factory function that gets passed the
environment of the first module to access this query.
The return value is then cached for all further accesses.
This allows you to lazily compute your shared properties only once and only if
accessed by any module.

```python
def factory(env):
    """
    Describe what this query is about, but don't document the `env` argument.

    :returns: an immutable object
    """
    # You can read the build environment, but cannot modify it here
    value = env["repo:module:option"]
    # This return data is cached, so this function is only called once.
    return {"key": value}

query = EnvironmentQuery(name="name",
                         factory=factory)
```
