#!/usr/bin/env python3
#
# Copyright (c) 2015-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os.path
import lbuild
import inspect

# ============================== HELPER FUNCTIONS =============================
def _hl(name, plain = False):
    if plain: return str(name);
    return str(lbuild.format._cw(str(name)).wrap("bold"))

def _rel(filename):
    return os.path.relpath(str(filename), os.getcwd())

def _bp(values):
    return "".join("    - {}\n".format(_hl(v)) for v in values)

def _dump(node):
    msg = ""
    if isinstance(node, lbuild.node.BaseNode):
        root = node.root
        msg = "\n\n\n{}".format(_hl("Current project configuration:"))
        # Render configuration if we know it
        if isinstance(root, lbuild.parser.Parser):
            msg += "\n\n{}".format(root._config.root.render())
        # Render as much tree in developer view as possible
        msg += "\n\n{}".format(root.render(lambda n: n.type in lbuild.node.BaseNode.Type))
    return msg

def _call_site(obj = None, plain = False):
    is_class = False
    if obj is None:
        file_prefix = os.path.dirname(os.path.abspath(__file__))
        caller = next( (stck for stck in inspect.stack() if not stck.filename.startswith(file_prefix)), None)
        if caller is None:
            return "In unknown location:\n"
        filename = caller.filename
        lineno = caller.lineno
        name = caller.function
        code_context = caller.code_context
    else:
        code_context, lineno = inspect.getsourcelines(obj)
        filename = inspect.getsourcefile(obj)
        name = obj.__name__
        is_class = inspect.isclass(obj)

    msg = "In file '{}:{}' in {} '{}':\n{}".format(
            _hl(_rel(filename), plain), _hl(lineno, plain),
            "class" if is_class else "function", _hl(name, plain),
            code_context[0])
    return msg


# ============================== BASE EXCEPTIONS ==============================
class LbuildException(Exception):
    """Base class for exception thrown by lbuild."""
    def __init__(self, message, node=None):
        super().__init__(message)
        self.node = node

class LbuildValidateException(Exception):
    pass

class LbuildArgumentException(LbuildException):
    pass

class LbuildAggregateException(LbuildException):
    """Collection of multiple exceptions."""
    def __init__(self, exceptions, suffix=None):
        msg = "\nERROR: ".join(str(exc) for exc in exceptions)
        if suffix is not None:
            msg += suffix
        super().__init__(msg)
        self.exceptions = exceptions

class LbuildDumpConfigException(LbuildException):
    def __init__(self, message, node=None):
        super().__init__(message.strip() + _dump(node), node)

class LbuildForwardException(LbuildException):
    def __init__(self, location, error):
        import traceback
        error_fmt = "".join(traceback.format_exception(type(error), error,
                                                       error.__traceback__, limit=-1))
        error_fmt = error_fmt.replace("lbuild.exception.Lbuild", "")
        msg = ("In '{}':\n\n{}"
               .format(_hl(location), _hl(error_fmt)))
        super().__init__(msg)
        self.module = location
        self.exception = error


# ========================== CONFIGURATION EXCEPTIONS =========================
class LbuildConfigException(LbuildException):
    def __init__(self, filename, message):
        message = "Configuration({}){}".format(_hl(_rel(filename)), message)
        super().__init__(message)
        self.filename = filename

class LbuildConfigNotFoundException(LbuildConfigException):
    def __init__(self, filename, parent=None):
        filename = _rel(filename)
        if parent is None:
            message = (" not found!\n"
                "Hint: Check your command line call:\n\n"
                "    lbuild -c {} discover\n"
                .format(_hl(filename)))
        else:
            message = (" not found!\n"
                "Hint: Check your configuration paths in '{}':\n\n"
                "    <extends>{}</extends>\n"
                .format(_hl(parent), _hl(filename)))
        super().__init__(filename, message)

class LbuildConfigNoReposException(LbuildConfigException):
    def __init__(self, parser):
        message = (": no repositories loaded!\n"
            "Hint: Add a path to one or more repositories, either in your configuration files:\n\n"
            "    <repositories>\n"
            "      <repository>\n"
            "        <path>{0}</path>\n"
            "      </repository>\n"
            "    </repositories>\n\n"
            "Or via the command line:\n\n"
            "    lbuild -r {0} discover"
            "{1}"
            .format(_hl("path/to/repo.lb"), _dump(parser)))
        super().__init__(parser._config.filename, message)

class LbuildConfigNoModulesException(LbuildConfigException):
    def __init__(self, parser):
        message = (": no modules selected to build!\n"
            "Hint: Add one or more modules either in your configuration files:\n\n"
            "    <modules>\n"
            "      <module>{0}</module>\n"
            "    </modules>\n\n"
            "Or via the command line:\n\n"
            "    lbuild build -m {0}"
            .format(_hl("repo:module")) + _dump(parser))
        super().__init__(parser._config.filename, message)

class LbuildConfigAddNotFoundException(LbuildConfigException):
    def __init__(self, repo, filename):
        filename = _rel(filename)
        message = (" not found!\n{}\n"
            "Hint: Check your config paths in '{}':\n\n"
            "   def init(repo):\n"
            "       repo.add_configuration(name, \"{}\", description)"
            .format(_call_site(repo._functions['init']),
                    _hl(_rel(repo._filename)), _hl(filename)))
        super().__init__(filename, message)
        self.node = repo

class LbuildConfigAliasNotFoundException(LbuildConfigException):
    def __init__(self, parser, alias):
        message = (": alias '{}' not found in any repository!"
                   .format(_hl(alias)) + _dump(parser))
        filename = next( (f for f, a in parser._config_flat._extends.items() if alias in a), None)
        super().__init__(filename, message)

class LbuildConfigAliasAmbiguousException(LbuildConfigException):
    def __init__(self, parser, alias, matches):
        aliases = _bp(sorted(c.fullname for c in matches))
        message = (": alias '{}' is ambiguous!\n"
                   "Hint: Found multiple matches:\n\n{}"
                   .format(_hl(alias), aliases) + _dump(parser))
        filename = next( (f for f, a in parser._config_flat._extends.items() if alias in a), None)
        super().__init__(filename, message)


# ============================= OPTION EXCEPTIONS =============================
class LbuildOptionException(LbuildException):
    def __init__(self, message, option):
        msg = ("{}({}){}\n{}\n"
               .format(option.class_name, _hl(_rel(option.fullname)),
                       message, option.description))
        super().__init__(msg, option)

class LbuildOptionConstructionException(LbuildOptionException):
    def __init__(self, option, reason):
        msg = ": invalid construction!\n{}\n{}\n".format(_call_site(), _hl(reason))
        super().__init__(msg, option)

class LbuildOptionInputException(LbuildOptionException):
    def __init__(self, option, value, reason):
        msg = (": input '{}' is invalid! {}\n"
               .format(_hl(value), _hl(reason)))
        super().__init__(msg, option)

class LbuildOptionRequiredInputException(LbuildOptionException):
    def __init__(self, option):
        msg = " requires an input value!\n"
        super().__init__(msg, option)

class LbuildOptionRequiredInputsException(LbuildAggregateException):
    def __init__(self, options):
        exceptions = {LbuildOptionRequiredInputException(o) for o in options}
        super().__init__(exceptions, _dump(next(iter(options))))


# ============================== QUERY EXCEPTIONS =============================
class LbuildQueryException(LbuildException):
    def __init__(self, message, query):
        msg = "{}({}){}\n".format(query.class_name, _hl(_rel(query.name)), message)
        super().__init__(msg, query)

class LbuildQueryConstructionException(LbuildQueryException):
    def __init__(self, query, reason):
        msg = ": invalid construction!\n{}\n{}\n".format(_call_site(), _hl(reason))
        super().__init__(msg, query)


# ============================= PARSER EXCEPTIONS =============================
class LbuildParserDuplicateRepoException(LbuildDumpConfigException):
    def __init__(self, parser, repo, conflict):
        msg = ("Repository({}) conflicts with existing Repository!\n{}\n"
               "Hint: This Repository from '{}':\n\n"
               "    >>> {}\n\n"
               "conflicts with this Repository from '{}':\n\n"
               "    >>> {}\n"
               .format(_hl(repo.name), _call_site(repo._functions['init']),
                       _hl(_rel(repo._filename)), lbuild.format.format_node(repo, 0, 0),
                       _hl(_rel(conflict._filename)), lbuild.format.format_node(conflict, 0, 0)))
        super().__init__(msg, parser)

class LbuildParserAddRepositoryNotFoundException(LbuildDumpConfigException):
    def __init__(self, parser, filename):
        msg = ("Repository file '{0}' not found!\n"
               "Hint: Check your command line call:\n\n"
               "    lbuild -r {0} discover\n\n"
               "Hint: Check your repository paths in '{1}':\n\n"
               "    <repositories>\n"
               "      <repository>\n"
               "        <path>{0}</path>\n"
               "      </repository>\n"
               "    </repositories>\n\n"
               .format(_hl(_rel(filename)), _hl(parser._config.filename)))
        super().__init__(msg, parser)

class LbuildParserCannotResolveDependencyException(LbuildDumpConfigException):
    def __init__(self, parser, error):
        is_ambiguos = isinstance(error, LbuildResolverAmbiguousMatchException)
        msg = ("Cannot resolve {}dependency '{}' of Module({})!\n{}\n"
               .format("ambiguous " if is_ambiguos else "",
                       _hl(error.query), _hl(error.node.fullname),
                       _call_site(error.node._functions['prepare'])))
        if is_ambiguos:
            msg += "Hint: Found these results:\n\n{}".format(
                            _bp(lbuild.format.format_node(r, 0, 0) for r in error.results))
        else:
            msg += ("Hint: Did you use the full module name?\n"
                    "      Is the module available and selected?\n")
        super().__init__(msg, parser)

class LbuildParserNodeNotFoundException(LbuildDumpConfigException):
    def __init__(self, parser, query, types=None):
        typestr = {"types": "", "plural": "Is the node"}
        if types is not None:
            types = lbuild.utils.listify(types)
            is_plural = len(types) > 1
            types = [_hl(t.name.capitalize()) for t in types]
            if is_plural:
                types = ", ".join(types)
                typestr["types"] = " of types {}".format(types)
                typestr["plural"] = "Are the {}".format(types)
            else:
                typestr["types"] = " of type {}".format(types[0])
                typestr["plural"] = "Is the {}".format(types[0])
        msg = ("Cannot resolve name '{}'{types}!\n\n"
               "Hint: Did you use the full name?\n"
               "      {plural} available and selected?\n"
               "      Check your command line and config files.\n"
               .format(_hl(query), **typestr))
        super().__init__(msg, parser)

class LbuildParserRepositoryEmptyException(LbuildDumpConfigException):
    def __init__(self, repo):
        msg = ("Repository({}) in '{}' did not add any modules!\n\n"
               "Hint: Add module files in the '{}' function:\n\n"
               "    prepare(repo, options):\n"
               "        repo.add_modules({})\n"
               "        repo.add_modules_recursive({})\n"
               .format(_hl(repo.fullname), _hl(_rel(repo._filename)),
                       _hl("prepare"), _hl('"path/to/module.lb"'), _hl('"directory"')))
        super().__init__(msg, repo)

class LbuildParserDuplicateModuleException(LbuildDumpConfigException):
    def __init__(self, parser, error):
        msg = ("{}({}) already has a submodule named '{}'!\n{}"
               .format(error.parent.class_name, _hl(error.parent.fullname),
                       _hl(error.child.fullname), error.hint))
        super().__init__(msg, parser)

# ============================= MODULE EXCEPTIONS =============================
class LbuildModuleNoNameException(LbuildDumpConfigException):
    def __init__(self, module): # ModuleInit
        msg = ("The '{}' function must set a module name!\n{}\n"
               "Hint:\n\n"
               "    def init(module):\n"
               "        {}"
               .format(_hl("init"), _call_site(module.functions['init']),
                       _hl("module.name = \":parent:name\"")))
        super().__init__(msg, module.repository)

class LbuildModuleNoReturnAvailableException(LbuildDumpConfigException):
    def __init__(self, module): # ModuleInit
        msg = ("The '{}' function of Module({}) must return a {}!\n{}\n"
               "Hint: The return value indicates whether or not this module"
               "is available given the repository options:\n\n"
               "    def prepare(module, options):\n"
               "        is_available = {{check repo options}}\n"
               "        {} is_available\n"
               .format(_hl("prepare"), _hl(module.fullname), _hl("boolean"),
                       _call_site(module.functions['prepare']),
                       _hl("return")))
        super().__init__(msg, module.repository)

class LbuildModuleParentNotFoundException(LbuildDumpConfigException):
    def __init__(self, module, parent): # Module
        msg = ("The parent '{}' for Module({}) in '{}' cannot be found!\n"
               "Hint: Make sure the parent module exists and is available for these repository options!"
               .format(_hl(parent), _hl(module.fullname), _hl(_rel(module._filename))))
        super().__init__(msg, module._repository)

class LbuildModuleDuplicateChildException(LbuildDumpConfigException):
    def __init__(self, module, error):
        msg = "{}{}\n{}".format(
                error.prompt, _call_site(module._functions["prepare"]), error.hint)
        super().__init__(msg, error.node)


# ============================ BUILDLOG EXCEPTIONS ============================
class LbuildBuildlogOverwritingFileException(LbuildException):
    def __init__(self, module, file, conflict): # RepositoryInit
        msg = ("Module({}) is overwriting file '{}'!\n{}\n"
               "Hint: File previously generated by Module({})!"
               .format(_hl(module), _hl(_rel(file)), _call_site(), _hl(conflict)))
        super().__init__(msg)


# =========================== REPOSITORY EXCEPTIONS ===========================
class LbuildRepositoryNoNameException(LbuildDumpConfigException):
    def __init__(self, parser, repo): # RepositoryInit
        msg = ("The '{}' function must set a repo name!\n{}\n"
               "Hint:\n\n"
               "    def init(repo):\n"
               "        {}"
               .format(_hl("init"), _call_site(repo._functions['init']),
                       _hl("repo.name = \":parent:name\"")))
        super().__init__(msg, parser)

class LbuildRepositoryAddModuleNotFoundException(LbuildDumpConfigException):
    def __init__(self, repo, path):
        msg = ("Module file '{}' not found!\n{}\n"
               "Hint: Use '{}' or '{}' for relative paths."
               .format(_hl(_rel(path)), _call_site(),
                       _hl("localpath(path)"), _hl("repopath(path)")))
        super().__init__(msg, repo)

class LbuildRepositoryAddModuleRecursiveNotFoundException(LbuildDumpConfigException):
    def __init__(self, repo, path):
        msg = ("Found no module files in '{}'!\n{}\n"
               "Hint: Use '{}' or '{}' for relative paths."
               .format(_hl(_rel(path)), _call_site(),
                       _hl("localpath(path)"), _hl("repopath(path)")))
        super().__init__(msg, repo)

class LbuildRepositoryDuplicateChildException(LbuildDumpConfigException):
    def __init__(self, parser, repo, error):
        msg = "{}{}\n{}".format(error.prompt, _call_site(repo._functions["init"]), error.hint)
        super().__init__(msg, repo)


# ============================== NODE EXCEPTIONS ==============================
class LbuildNodeMissingFunctionException(LbuildDumpConfigException):
    def __init__(self, repo, filename, error, submodule=None):
        msg = ("{}{} is missing the '{}' function!\n{}\n"
               "Hint: Required functions are:\n\n{}\n"
               "Hint: Optional functions are:\n\n{}"
               .format("Repository" if isinstance(repo, lbuild.repository.RepositoryInit) else "Module",
                       " file in '{}'".format(_hl(_rel(filename))) if submodule is None else "",
                       _hl(error.missing),
                       "" if submodule is None else _call_site(submodule.__class__),
                       _bp(error.required), _bp(error.optional)))
        super().__init__(msg, repo)

class LbuildNodeDuplicateChildException(LbuildDumpConfigException):
    def __init__(self, parent, child, conflict):
        prompt = ("{}({}) conflicts with existing {} for parent '{}'!\n"
                  .format(_hl(child.class_name), _hl(child.fullname),
                          _hl(conflict.class_name), _hl(parent.fullname)))
        hint = ("Hint: This {}{}:\n\n"
                "    >>> {}\n\n"
                "conflicts with this {}{}:\n\n"
                "    >>> {}\n"
                .format(_hl(child.class_name), "" if child._filename is None else
                            " defined in '{}'".format(_hl(_rel(child._filename))),
                        lbuild.format.format_node(child, 0, 0),
                        _hl(conflict.class_name), "" if conflict._filename is None else
                            " defined in '{}'".format(_hl(_rel(conflict._filename))),
                        lbuild.format.format_node(conflict, 0, 0)))
        super().__init__(prompt + hint, parent._repository)
        self.prompt = prompt
        self.hint = hint
        self.parent = parent
        self.child = child
        self.conflict = conflict

class LbuildNodeConstructionException(LbuildDumpConfigException):
    def __init__(self, repo, node, reason):
        msg = "'{}({})':\n{}\n{}".format(node.__class__.__name__, _hl(node.name),
                                         _call_site(), _hl(reason))
        super().__init__(msg, repo)


# ============================ RESOLVER EXCEPTIONS ============================
class LbuildResolverException(LbuildDumpConfigException):
    def __init__(self, msg, node):
        super().__init__(msg, node)

class LbuildResolverSearchException(LbuildResolverException):
    def __init__(self, resolver, result, reason):
        msg = "{}({}) {}".format(_hl(result.class_name), _hl(result.fullname), reason)
        super().__init__(msg, resolver._node)
        self.result = result

class LbuildResolverNoMatchException(LbuildResolverException):
    def __init__(self, node, query):
        msg = ("Cannot resolve name '{}' in the context of '{}'!\n{}\n"
               "Hint: Did you use the full name?\n"
               "      Is the module or option available?\n"
               "      Did you depend on the respective module?\n"
               .format(_hl(query), _hl(node.fullname), _call_site()))
        super().__init__(msg, node)
        self.query = query

class LbuildResolverAmbiguousMatchException(LbuildResolverException):
    def __init__(self, node, query, results):
        msg = ("Cannot resolve ambiguous name '{}' in the context of '{}'!\n{}\n"
               "Hint: Found these results:\n\n{}"
               .format(_hl(query), _hl(node.fullname), _call_site(),
                       _bp(r.fullname for r in results)))
        super().__init__(msg, node)
        self.query = query
        self.results = results


# =========================== ENVIRONMENT EXCEPTIONS ==========================
class LbuildEnvironmentException(LbuildException):
    def __init__(self, msg, module):
        super().__init__("In Module '{}': {}".format(_hl(module.fullname), msg), module)

class LbuildEnvironmentTemplateException(LbuildEnvironmentException):
    def __init__(self, module, src, error):
        import jinja2
        if isinstance(error, (jinja2.exceptions.TemplateAssertionError,
                              jinja2.exceptions.TemplateSyntaxError)):
            snippet = error.source.splitlines()
            snippet = snippet[max(0, error.lineno-2):
                              min(error.lineno+2, len(snippet))]
            snippet = "\n" + "\n".join(snippet)
            path = "{}:{}".format(error.filename, error.lineno)
            message = "\n{}: {}".format(error.__class__.__name__, error)
        else:
            path = src
            message = "\n{}: {}".format(error.__class__.__name__, error)
            snippet = ""

        msg = ("\n{}\nError in template '{}':{}\n{}"
               .format(_call_site(), _hl(_rel(path)), snippet, _hl(message)))
        super().__init__(msg, module)

class LbuildEnvironmentCollectException(LbuildEnvironmentException):
    def __init__(self, module, reason):
        msg = ("Failed to collect these values!\n{}\n{}"
               .format(_call_site(), reason))
        super().__init__(msg, module)

class LbuildEnvironmentFileNotFoundException(LbuildEnvironmentException):
    def __init__(self, module, path):
        msg = ("File or directory not found!\n{}\n"
               "Source path '{}' does not exist!\n"
               "Hint: Use '{}' or '{}' for relative paths."
               .format(_call_site(), _hl(_rel(path)),
                       _hl("localpath(path)"), _hl("repopath(path)")))
        super().__init__(msg, module)

class LbuildEnvironmentFileOutsideRepositoryException(LbuildEnvironmentException):
    def __init__(self, module, path):
        msg = ("Cannot access files outside of the repository!\n{}\n"
               "Path '{}' is above repository location '{}'!\n"
               "Hint: Use '{}' or '{}' for relative paths."
               .format(_call_site(), _hl(_rel(path)), _hl(_rel(module.repository._filepath)),
                       _hl("localpath(path)"), _hl("repopath(path)")))
        super().__init__(msg, module)

class LbuildEnvironmentArchiveNoFileException(LbuildEnvironmentException):
    def __init__(self, module, path, members):
        msg = ("Archive has no file or folder called '{}'!\n{}\n"
               "Hint: Available files and folders are:\n\n{}"
               .format(_hl(_rel(path)), _call_site(), _bp(members)))
        super().__init__(msg, module)


# ============================== UTILS EXCEPTIONS =============================
class LbuildUtilsFunctionNotFoundException(LbuildException):
    def __init__(self, missing, required, optional):
        super().__init__("Function '{}' not found!".format(_hl(missing)))
        self.missing = str(missing)
        self.required = required
        self.optional = optional

