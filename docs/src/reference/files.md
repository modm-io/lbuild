# Files

*lbuild* properly imports the declared repository and modules files, so you can
use everything that Python has to offer.
In addition to `import`ing your required modules, *lbuild* provides these
global functions and classes for use in all files:

- `localpath(path)`: remaps paths relative to the currently executing file.
  All paths are already interpreted relative to this file, but you can use this
  to be explicit.
- `repopath(path)`: remaps paths relative to the repository file. You should use
  this to reference paths that are not related to your module.
- `listify(obj)`: turns obj into a list, maps `None` to empty list.
- `listrify(obj)`: turns obj into a list of strings, maps `None` to empty list.
- `uniquify(obj)`: turns obj into a unique list, maps `None` to empty list.
- `FileReader(path)`: reads the contents of a file and turns it into a string.
- `{*}Option(...)`: classes for describing options, [see Options](options.md).
- `{*}Query(...)`: classes for sharing code and data, [see Queries](queries.md).
- `{*}Collector(...)`: classes for describing metadata sinks, [see Collectors](collectors.md).
- `Alias(...)`: links to other nodes, [see Aliases](aliases.md).
- `Configuration(...)`: links to a configuration inside the repository.
