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
9. `module:validate(env)` submodules-first, *optional*
10. `module:build(env)` submodules-first
11. `repo:build(env)`: *optional*
12. `module:post_build(env)`: submodules-first, *optional*
