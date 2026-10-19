# Name Resolution

*lbuild* manages repositories, modules and options in a tree structure and
serializes identification into unique string using `:` as hierarchy delimiters.
Any identifier provided via the command line, configuration, repository or
module files use the same resolver, which allows using *partially-qualified*
identifiers. In addition, globbing for multiple identifiers using fnmatch
semantics is supported.

The following rules for resolving identifiers apply:

1. A fully-qualified identifier specifies all parts: `repo:module:option`.
2. A partially-qualified identifier adds fnmatch wildcarts: `*:m.dule:opt*`.
3. `*` wildcarts for entire hierarchies can be ommitted: `::option`
4. A special wildcart is `:**`, which globs for everything below the current
   hierarchy level: `repo:**` selects all in `repo`, `repo:module:**` all in
   `repo:module`, etc.
5. Wildcarts are resolved in reverse hierarchical order. Therefore, `::option`
   may be unique within the context of `:module`, but not within the entire
   project.
6. For accessing direct children, you may specify their name without any
   delimiters: `option` within the context of `:module` will resolve to
   `:module:option`.

Partial identifiers were introduced to reduce verbosity and aid refactoring,
it is therefore recommended to:

1. Omit the repository name for accessing modules and options within the same
   repository.
2. Accessing a module's options with their name directly.
