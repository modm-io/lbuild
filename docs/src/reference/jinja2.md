# Jinja2 Configuration

*lbuild* uses the [Jinja2 template engine][jinja2] with the following global
configuration:

- Line statements start with `%% statement`.
- Line comments start with `%# comment`.
- Undefined variables throw an exception instead of being ignored.
- Global extensions: `jinja2.ext.do`.
- Global substitutions are:
  + `time`: `strftime("%d %b %Y, %H:%M:%S")`
  + `options`: an option resolver in the context of the current module.
  + `collector_values`: a resolver for the values of collectors.
- Filters are the ones added with `repo.add_filter(...)` and
  `module.add_filter(...)`, plus the `filters` passed to `env.template(...)`.
- `{% include %}` and `{% import %}` paths are relative to the including
  template.

```jinja
%% for name in options["::instances"]
#include "{{ name }}.hpp"
%% endfor
%# Includes a template next to this template
%% include "common.hpp.in"
```

[jinja2]: https://jinja.palletsprojects.com
