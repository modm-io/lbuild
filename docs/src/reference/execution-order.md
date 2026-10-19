# Execution order

*lbuild* executes in this order:

1. `repository:init()`
2. Create repository options
3. `repository:prepare(repo-options)`
4. Find all modules in repositories
5. `module:init()`
6. `module:prepare(repo-options)`
7. Create module options
8. Resolve module dependencies
9. `module:validate(env)` for all modules, *optional*
10. `module:build(env)` and `repo:build(env)`, *optional*
11. `module:post_build(env)`, *optional*

The validate, build and post-build steps all walk the modules in the same order:

- Modules are grouped by their `module.order`, with lower orders first. A
  top-level module uses the sum of the orders of itself and all its built
  submodules, which then inherit this order. Repositories have order 0.
- Within a group, submodules are always handled before their parent modules,
  and repositories after the modules of their group.
- Modules of the same depth are handled in random order, so you must not rely
  on the order between sibling modules.

All modules are validated before any module is built and all modules are built
before any post-build step runs.
