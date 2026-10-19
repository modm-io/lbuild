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

[jinja2]: http://jinja.pocoo.org
