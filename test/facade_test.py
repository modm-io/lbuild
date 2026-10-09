#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

"""
Tests the interface that repository and module files see, one small
repository per test. This covers the parts that the library in
`usage_test.py` does not need, including everything that is deprecated.
"""

import os
import sys
import json
import shutil
import logging
import tarfile
import zipfile
import tempfile
import textwrap
import unittest
import warnings
from os.path import join

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.exception as le

# Lets the repository and module files tell the test what they have seen
PRELUDE = '''
import json, os
def observe(**values):
    data = {}
    if os.path.exists("observed.json"):
        with open("observed.json") as file:
            data = json.load(file)
    data.update(values)
    with open("observed.json", "w") as file:
        json.dump(data, file)

def public(obj):
    return sorted(name for name in dir(obj) if not name.startswith("_"))
'''

REPO = '''
def init(repo):
    repo.name = "repo"

def prepare(repo, options):
    repo.add_modules_recursive(".")
'''

# For projects with files that only look like modules
REPO_SINGLE = REPO.replace('_recursive(".")', '("{}")')

MODULE = '''
def init(module):
    module.name = "{name}"

def prepare(module, options):
    return True

def build(env):
    pass
'''


class FacadeTestCase(unittest.TestCase):

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)

        for module, name in ((lbuild.format, "PLAIN"),
                             (lbuild.environment, "SIMULATE"),
                             (lbuild.environment, "SYMLINK_ON_COPY")):
            self.addCleanup(setattr, module, name, getattr(module, name))
        lbuild.format.PLAIN = True

    def project(self, files):
        """Writes the files of a project, `.lb` files may use `observe()`."""
        files = dict(files)
        files.setdefault("repo.lb", REPO)
        for path, content in files.items():
            os.makedirs(os.path.dirname(join(self.root, path)), exist_ok=True)
            if path.endswith(".lb"):
                content = PRELUDE + textwrap.dedent(content)
            with open(join(self.root, path), "w" if isinstance(content, str) else "wb") as file:
                file.write(content)

    def load(self, *options, collectors=None, repositories="repo.lb"):
        builder = lbuild.api.Builder(cwd=self.root, options=list(options),
                                     collectors=collectors, outpath=join(self.root, "out"))
        builder.load(repositories)
        return builder

    def build(self, *options, modules="repo:**", **kw):
        return self.load(*options, **kw).build(modules=modules)

    def module(self, source, *options, **kw):
        """Builds a single module and returns what it observed."""
        self.project({"module.lb": source})
        self.build(*options, **kw)
        return self.observed()

    def observed(self):
        with open("observed.json") as file:
            return json.load(file)

    def read(self, path):
        with open(join(self.root, path)) as file:
            return file.read()

    def archive(self):
        """Returns the content of a zip archive with one file."""
        with tempfile.TemporaryDirectory() as folder:
            with open(join(folder, "file.txt"), "w") as file:
                file.write("archived")
            with open(shutil.make_archive(join(folder, "archive"), "zip", folder, "file.txt"),
                      "rb") as file:
                return file.read()

    def files(self, path="out"):
        return sorted(os.path.relpath(join(base, name), join(self.root, path))
                      for base, _, names in os.walk(join(self.root, path)) for name in names)


class RepositoryFacadeTest(FacadeTestCase):

    GLOBALS = ["Alias", "BooleanCollector", "BooleanOption", "CallableCollector",
               "Configuration", "EnumerationCollector", "EnumerationOption",
               "EnvironmentQuery", "FileReader", "Module", "NumericCollector",
               "NumericOption", "PathCollector", "PathOption", "Query", "SetOption",
               "StringCollector", "StringOption", "ValidateException", "json",
               "listify", "listrify", "localpath", "observe", "os", "public",
               "repopath", "uniquify"]

    def test_should_provide_interface(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                observe(init=public(repo))

            def prepare(repo, options):
                repo.add_modules_recursive(".")
                observe(prepare=public(repo))

            def build(env):
                observe(build=public(env))
            ''', "module.lb": MODULE.format(name="module")})
        self.build()

        self.assertEqual({
            "init": ["add_alias", "add_configuration", "add_filter", "add_ignore_patterns",
                     "add_list_option", "add_option", "add_query", "add_set_option",
                     "description", "format_description", "format_short_description", "name"],
            "prepare": ["add_modules", "add_modules_recursive", "add_submodule", "description",
                        "find_modules_recursive", "format_description",
                        "format_short_description", "glob", "name"],
            "build": EnvironmentFacadeTest.BUILD,
        }, self.observed())

    def test_should_provide_globals(self):
        self.project({"repo.lb": '''
            observe(globals=sorted(name for name in dir() if not name.startswith("_")),
                    localpath=localpath("a", "b"), repopath=repopath("c"),
                    listify=[listify(None), listify(1), listify([1, 2], (3,), "45")],
                    listrify=listrify(1, [2, None]), uniquify=uniquify([3, 1, 3, 2]))

            def init(repo):
                repo.name = "repo"

            def prepare(repo, options):
                repo.add_modules_recursive(".")
            ''', "module.lb": MODULE.format(name="module")})
        self.load()
        observed = self.observed()

        self.assertEqual(self.GLOBALS, observed["globals"])
        self.assertEqual(join(self.root, "a", "b"), observed["localpath"])
        self.assertEqual(join(self.root, "c"), observed["repopath"])
        self.assertEqual([[], [1], [1, 2, 3, "45"]], observed["listify"])
        self.assertEqual(["1", "2", "None"], observed["listrify"])
        self.assertEqual([1, 2, 3], observed["uniquify"])

    def test_should_read_properties(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.description = "Text"
                observe(init=[repo.name, repo.description,
                              repo.format_description.__name__,
                              repo.format_short_description.__name__])

            def prepare(repo, options):
                repo.add_modules_recursive(".")
                observe(prepare=[repo.name, repo.description,
                                 repo.format_description.__name__,
                                 repo.format_short_description.__name__])
            ''', "module.lb": MODULE.format(name="module")})
        self.load()

        self.assertEqual({
            "init": ["repo", "Text", "format_description", "format_short_description"],
            "prepare": ["repo", ">> repo  [Repository]\n\nText", "format_description",
                        "format_short_description"],
        }, self.observed())

    def test_should_add_modules(self):
        self.project({"repo.lb": '''
            class Inline(Module):
                def __init__(self, name):
                    self.name = name
                def init(self, module):
                    module.name = self.name
                def prepare(self, module, options):
                    return True
                def build(self, env):
                    pass

            def init(repo):
                repo.name = "repo"

            def prepare(repo, options):
                observe(glob=repo.glob("*/[bc].lb"))
                repo.add_modules("a.lb", ["sub/b.lb"], Inline("inline"))
                repo.add_modules(repo.glob("*/c.lb"), [Inline("list")])
                repo.add_submodule(Inline("single"))
                repo.add_submodule("d.lb")
            ''',
                      "a.lb": MODULE.format(name="a"),
                      "sub/b.lb": MODULE.format(name="b"),
                      "sub/c.lb": MODULE.format(name="c"),
                      "d.lb": MODULE.format(name="d"),
                      "unused.lb": MODULE.format(name="unused")})
        modules = self.load().parser.modules

        self.assertEqual(["repo:a", "repo:b", "repo:c", "repo:d", "repo:inline", "repo:list",
                          "repo:single"], sorted(modules))
        self.assertEqual([join(self.root, "sub/b.lb"), join(self.root, "sub/c.lb")],
                         sorted(self.observed()["glob"]))

    def test_should_add_modules_recursive(self):
        modules = {name: MODULE.format(name=name.replace("/", "_").split(".")[0])
                   for name in ("module.lb", "a/module.lb", "a/b/module.lb", "a/other.lb",
                                "c/extra.lb", "c/skip_extra.lb", "d/module.lb")}

        def load(*calls):
            self.project(dict(modules, **{"repo.lb": '''
                def init(repo):
                    repo.name = "repo"
                    # Only the name of a module file is matched, not its path
                    repo.add_ignore_patterns("skip_*")

                def prepare(repo, options):
                    {}
                '''.format("\n                    ".join(calls))}))
            return sorted(self.load().parser.modules)

        self.assertEqual(["repo:a_b_module", "repo:a_module", "repo:d_module", "repo:module"],
                         load('repo.add_modules_recursive()'))
        self.assertEqual(["repo:a_b_module", "repo:a_module"],
                         load('repo.add_modules_recursive("a")'))
        self.assertEqual(["repo:c_extra"],
                         load('repo.add_modules_recursive(basepath="c", modulefile="*.lb")'))
        self.assertEqual(["repo:a_module", "repo:a_other"],
                         load('repo.add_modules_recursive("a", "*.lb", ignore="module.l?")',
                              'repo.add_modules("a/module.lb")'))
        self.assertEqual(["repo:a_other", "repo:d_module"],
                         load('repo.add_modules_recursive("a", "o*.lb", ["x", "y"])',
                              'repo.add_modules_recursive("d")'))

        with self.assertRaises(le.LbuildRepositoryAddModuleRecursiveNotFoundException):
            load('repo.add_modules_recursive("c")')
        with self.assertRaises(le.LbuildRepositoryAddModuleNotFoundException):
            load('repo.add_modules("missing.lb")')
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(["repo:d_module"], load('repo.find_modules_recursive("d")'))

    def test_should_not_find_modules_twice(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"

            def prepare(repo, options):
                repo.add_modules_recursive(".")
                repo.add_modules("module.lb")
            ''', "module.lb": MODULE.format(name="module")})
        with self.assertRaises(le.LbuildParserDuplicateModuleException):
            self.load()

    def test_should_add_options_queries_and_aliases(self):
        self.project({"repo.lb": '''
            def answer():
                """The answer."""
                return 42

            def init(repo):
                repo.name = "repo"
                repo.add_option(StringOption(name="string", description="", default="text"))
                repo.add_set_option(EnumerationOption(name="set", description="",
                                                      enumeration=["a", "b", "c"]), default="a")
                repo.add_list_option(NumericOption(name="list", description=""), default=[1, 1])
                repo.add_query(Query(function=answer))
                repo.add_query(EnvironmentQuery(name="strings", factory=lambda env: env[":string"] * 2))
                repo.add_alias(Alias(name="text", destination="string", description="Renamed"))

            def prepare(repo, options):
                repo.add_modules_recursive(".")
                observe(prepare=[options["string"], options[":set"], options["repo:list"],
                                 options.get("unknown", "default"), "string" in options,
                                 "unknown" in options])

            def build(env):
                observe(build=[env["string"], env[":set"], env.query("answer")(),
                               env.query(":strings"), env.has_query("answer"),
                               env.has_option("set")])
            ''', "module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                observe(module_prepare=[options[":string"], options["repo:set"]])
                return True

            def build(env):
                observe(module_build=[env[":string"], env[":text"], env.query(":answer")(),
                                      env.query("repo:strings")])
            '''})
        with self.assertLogs("lbuild.node", logging.WARNING) as logs:
            self.build("repo:string=value", "repo:set=c,b,c", "repo:list=3,3")

        self.assertEqual({
            "prepare": ["value", ["c", "b"], [3, 3], "default", True, False],
            "build": ["value", ["c", "b"], 42, "valuevalue", True, True],
            "module_prepare": ["value", ["c", "b"]],
            "module_build": ["value", "value", 42, "valuevalue"],
        }, self.observed())
        self.assertIn("'repo:text' has been moved to 'string'", logs.output[0])

    def test_should_require_repository_option(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.add_option(NumericOption(name="required", description=""))

            def prepare(repo, options):
                observe(prepared=True)
                repo.add_modules_recursive(".")
            ''', "module.lb": MODULE.format(name="module")})

        builder = self.load()
        self.assertFalse(os.path.exists("observed.json"))
        with self.assertRaises(le.LbuildOptionRequiredInputsException) as error:
            builder.build()
        self.assertIn("repo:required", str(error.exception))

        self.build("repo:required=1")
        self.assertEqual({"prepared": True}, self.observed())

    def test_should_namespace_filters(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.add_filter("repo.twice", lambda value: value * 2)
                repo.add_filter("thrice", lambda value: value * 3)

            def prepare(repo, options):
                repo.add_modules_recursive(".")
            ''', "module.lb": '''
            def init(module):
                module.name = "module"
                module.add_filter("repo.negate", lambda value: -value)
                module.add_filter("square", lambda value: value * value)

            def prepare(module, options):
                return True

            def build(env):
                observe(has=[env.has_filter(name) for name in
                             ("repo.twice", "repo.thrice", "thrice", "repo.negate", "repo.square",
                              "square", "lbuild.indent", "lbuild.pad", "lbuild.split",
                              "lbuild.wordwrap", "lbuild.listify", "lbuild.unknown")],
                        call=[env.filter("repo.thrice")(2), env.filter("repo.square")(3),
                              env.filter("unknown"), env.filter("unknown", 4)])
                env.template("filters.txt.in")
            ''', "filters.txt.in": '{{ 2 | repo.twice }} {{ 2 | repo.thrice }} {{ 2 | repo.negate }} '
                                   '{{ 2 | repo.square }} {{ "a" | lbuild.pad(3) }}|'})

        with self.assertLogs("lbuild", logging.WARNING) as logs:
            self.build()

        self.assertEqual(["WARNING:lbuild.repository:Namespacing repository filter 'thrice' to "
                          "'repo.thrice'!",
                          "WARNING:lbuild.module:Namespacing module filter 'square' to "
                          "'repo.square'!"], logs.output)
        self.assertEqual({"has": [True, True, False, True, True, False, True, True, True, True,
                                  True, False],
                          "call": [6, 9, None, 4]}, self.observed())
        self.assertEqual("4 6 -2 4 a\t|", self.read("out/filters.txt"))

    @unittest.expectedFailure
    def test_should_not_share_filters_with_other_libraries(self):
        # FIXME: all nodes share one global dictionary of filters
        self.test_should_namespace_filters()
        os.remove("observed.json")
        self.project({"repo.lb": REPO.replace('"repo"', '"other"'), "module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                observe(has=env.has_filter("repo.twice"))
            '''})
        self.build(modules="other:**")
        self.assertEqual({"has": False}, self.observed())

    def test_should_add_configurations(self):
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.add_configuration(Configuration("single", "One file", "single.xml"))
                repo.add_configuration(Configuration("many", "Files", {"a": "single.xml",
                                                                         "b": localpath("b.xml")},
                                                     default="a"))
                repo.add_configuration("old", "single.xml", "Positional arguments")

            def prepare(repo, options):
                repo.add_modules_recursive(".")
            ''', "module.lb": MODULE.format(name="module"),
                      "single.xml": "<library><modules><module>repo:module</module></modules></library>",
                      "b.xml": "<library/>"})
        with self.assertWarns(DeprecationWarning):
            repo = self.load().parser.repositories["repo"]

        self.assertEqual({"repo:single": "", "repo:many": "a", "repo:old": ""},
                         {config.fullname: config.value for config in repo.configurations})

    def test_should_check_configurations(self):
        def load(configuration):
            self.project({"repo.lb": '''
                def init(repo):
                    repo.name = "repo"
                    repo.add_configuration({})

                def prepare(repo, options):
                    repo.add_modules_recursive(".")
                '''.format(configuration), "module.lb": MODULE.format(name="module"),
                          "single.xml": "<library/>"})
            self.load()

        with self.assertRaises(le.LbuildConfigAddNotFoundException):
            load('Configuration("name", "", "missing.xml")')
        with self.assertRaises(le.LbuildConfigNoDefaultException):
            load('Configuration("name", "", {"a": "single.xml"})')
        with self.assertRaises(le.LbuildRepositoryDuplicateChildException):
            load('Configuration("name", "", "single.xml"))\n'
                 '                    repo.add_configuration(Configuration("name", "", "single.xml")')

    @unittest.expectedFailure
    def test_should_relocate_all_configuration_paths(self):
        # FIXME: only the path of the default version is relative to the repository
        self.project({"repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.add_configuration(Configuration("name", "", {"a": "sub/a.xml", "b": "sub/b.xml"},
                                                     default="a"))

            def prepare(repo, options):
                repo.add_modules_recursive(".")
            ''', "module.lb": MODULE.format(name="module"),
                      "sub/a.xml": "<library/>",
                      "sub/b.xml": "<library><modules><module>repo:module</module></modules></library>"})
        os.mkdir("elsewhere")
        os.chdir("elsewhere")
        builder = lbuild.api.Builder(config="repo:name:b")
        builder.load(join(self.root, "repo.lb"))
        self.assertEqual(["repo:module"], builder.parser.config.modules)

    def test_should_fail_to_load_broken_repositories(self):
        def load(source):
            self.project({"repo.lb": source, "module.lb": MODULE.format(name="module")})
            self.load()

        with self.assertRaises(le.LbuildRepositoryNoNameException):
            load("def init(repo):\n    pass\ndef prepare(repo, options):\n    pass\n")
        with self.assertRaises(le.LbuildNodeMissingFunctionException):
            load("def init(repo):\n    repo.name = 'repo'\n")
        with self.assertRaises(le.LbuildParserRepositoryEmptyException):
            load("def init(repo):\n    repo.name = 'repo'\ndef prepare(repo, options):\n    pass\n")
        with self.assertRaises(le.LbuildForwardException) as error:
            load("def init(repo):\n    repo.name = 'repo'\n"
                 "def prepare(repo, options):\n    raise KeyError('oops')\n")
        self.assertIn("oops", str(error.exception))
        with self.assertRaises(le.LbuildForwardException):
            load("import does_not_exist\n")
        with self.assertRaises(le.LbuildNodeConstructionException):
            load("def init(repo):\n    repo.name = 'repo'\n"
                 "    repo.add_option(StringOption(name='a:b', description=''))\n"
                 "def prepare(repo, options):\n    pass\n")


class ModuleFacadeTest(FacadeTestCase):

    def test_should_provide_interface(self):
        observed = self.module('''
            def init(module):
                module.name = "module"
                observe(init=public(module))

            def prepare(module, options):
                observe(prepare=public(module))
                return True

            def build(env):
                pass
            ''')

        self.assertEqual({
            "init": ["add_filter", "description", "format_description",
                     "format_short_description", "name", "order", "parent"],
            "prepare": ["add_alias", "add_collector", "add_list_option", "add_modules",
                        "add_option", "add_query", "add_set_option", "add_submodule", "depends",
                        "description", "format_description", "format_short_description", "name",
                        "parent"],
        }, observed)

    def test_should_provide_globals(self):
        self.project({"sub/module.lb": MODULE.format(name="module") + '''
observe(globals=sorted(name for name in dir() if not name.startswith("_")),
        localpath=localpath("a"), repopath=repopath("b"),
        exception=PreBuildException is ValidateException)
'''})
        self.load()
        observed = self.observed()

        # the same as for the repository, plus the functions of the module
        self.assertEqual(["PreBuildException", "build", "init", "prepare"],
                         [name for name in observed["globals"]
                          if name not in RepositoryFacadeTest.GLOBALS])
        self.assertEqual(join(self.root, "sub/a"), observed["localpath"])
        self.assertEqual(join(self.root, "b"), observed["repopath"])
        self.assertTrue(observed["exception"])

    def test_should_read_properties(self):
        observed = self.module('''
            def init(module):
                module.name = "module"
                module.description = "Text"
                order = module.order
                module.order = 5
                observe(init=[module.name, module.description, order, module.order,
                              module.format_description.__name__])

            def prepare(module, options):
                observe(prepare=[module.name, module.description, module.parent,
                                 module.format_short_description.__name__])
                return True

            def build(env):
                pass
            ''')

        self.assertEqual({"init": ["module", "Text", 0, 5, "format_description"],
                          "prepare": ["module", "Text", "repo", "format_short_description"]},
                         observed)

    def test_should_name_modules(self):
        names = {"a.lb": "a", "b.lb": ":b", "c.lb": "repo:c", "d.lb": "a:d", "e.lb": ":a:e",
                 "f.lb": "repo:a:d:f"}
        self.project({path: MODULE.format(name=name) for path, name in names.items()})
        self.project({"repo.lb": REPO.replace('(".")', '(".", "?.lb")')})

        self.assertEqual(["repo:a", "repo:a:d", "repo:a:d:f", "repo:a:e", "repo:b", "repo:c"],
                         sorted(self.load().parser.modules))

    def test_should_set_parent(self):
        self.project({"a.lb": MODULE.format(name="a"), "b.lb": '''
            def init(module):
                module.name = "b"
                observe(before=module.parent)
                module.parent = "a"
                observe(after=module.parent)

            def prepare(module, options):
                return True

            def build(env):
                pass
            ''', "repo.lb": REPO.replace('(".")', '(".", "?.lb")')})
        with self.assertWarns(DeprecationWarning):
            modules = self.load().parser.modules

        self.assertEqual(["repo:a", "repo:a:b"], sorted(modules))
        self.assertEqual({"before": None, "after": "a"}, self.observed())

    def test_should_add_submodules(self):
        self.project({"module.lb": '''
            class Inline(Module):
                def __init__(self, name, children=()):
                    self.name = name
                    self.children = children
                def init(self, module):
                    module.name = self.name
                def prepare(self, module, options):
                    for child in self.children:
                        module.add_submodule(Inline(child))
                    return True
                def build(self, env):
                    observe(**{self.name: env.localpath("x")})

            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_submodule(Inline("a", children=["b"]))
                module.add_submodule("sub/file.lb")
                module.add_modules(Inline("c"), "sub/other.lb", Inline(":d"), Inline(":module:e"))
                return True

            def build(env):
                pass
            ''', "sub/file.lb": MODULE.format(name="file"),
                      "sub/other.lb": MODULE.format(name="other")})
        builder = self.load()
        builder.build(modules="repo:**")

        # Only names without a scope are placed below the parent module
        self.assertEqual(["repo:d", "repo:module", "repo:module:a", "repo:module:a:b",
                          "repo:module:c", "repo:module:e", "repo:module:file",
                          "repo:module:other"], sorted(builder.parser.modules))
        # Modules from a class live in the file that created them
        self.assertEqual({name: join(self.root, "x") for name in ("a", "b", "c", ":d", ":module:e")},
                         self.observed())

    def test_should_disable_modules(self):
        self.project({"module.lb": '''
            class Inline(Module):
                def init(self, module):
                    module.name = "child"
                def prepare(self, module, options):
                    observe(child=True)
                    return True
                def build(self, env):
                    pass

            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_submodule(Inline())
                return False

            def build(env):
                pass
            ''', "other.lb": MODULE.format(name="other"),
                      "repo.lb": REPO.replace('(".")', '(".", "*.lb")')})
        builder = self.load()

        # The submodule is prepared, but not available without its parent
        self.assertEqual(["repo:other"], sorted(builder.parser.modules))
        self.assertEqual({"child": True}, self.observed())
        with self.assertRaises(le.LbuildParserNodeNotFoundException):
            builder.build(modules="repo:module:child")

    def test_should_fail_to_load_broken_modules(self):
        def load(source, **files):
            self.project(dict({"module.lb": source}, **files))
            self.load()

        with self.assertRaises(le.LbuildModuleNoNameException):
            load(MODULE.format(name="module").replace('module.name = "module"', "pass"))
        with self.assertRaises(le.LbuildModuleNoReturnAvailableException):
            load(MODULE.format(name="module").replace("return True", "pass"))
        with self.assertRaises(le.LbuildNodeMissingFunctionException):
            load(MODULE.format(name="module").replace("def build", "def construct"))
        with self.assertRaises(le.LbuildNodeMissingFunctionException):
            load("class Empty(Module):\n    pass\n" + MODULE.format(name="module").replace(
                "return True", "module.add_submodule(Empty())\n    return True"))
        with self.assertRaises(le.LbuildForwardException):
            load(MODULE.format(name="module").replace("return True", "return 1 / 0"))
        with self.assertRaises(le.LbuildModuleParentNotFoundException):
            load(MODULE.format(name="missing:module"))
        with self.assertRaises(le.LbuildNodeConstructionException):
            load(MODULE.format(name="mod*ule"))
        with self.assertRaises(le.LbuildModuleDuplicateChildException):
            load(MODULE.format(name="module").replace("return True", '''
    module.add_option(BooleanOption(name="same", description=""))
    module.add_collector(StringCollector(name="same", description=""))
    return True'''))
        with self.assertRaises(le.LbuildParserDuplicateModuleException):
            load(MODULE.format(name="module"), **{"sub/module.lb": MODULE.format(name="module")})
        with self.assertRaises(FileNotFoundError):
            load(MODULE.format(name="module").replace(
                "return True", "module.add_submodule('missing.lb')\n    return True"))

    def test_should_depend_on_modules(self):
        def built(depends, *options):
            self.project({"module.lb": '''
                def init(module):
                    module.name = "module"

                def prepare(module, options):
                    module.add_option(EnumerationOption(
                        name="needs", description="", enumeration=["none", "b", "bc"],
                        default="none",
                        dependencies=lambda value: {{"none": None, "b": ":b",
                                                    "bc": [":b", "repo:c"]}}[value]))
                    {}
                    return True

                def build(env):
                    observe(has=[env.has_module(name) for name in (":a", ":b", ":c", ":a:child")])
                '''.format(depends),
                          "a.lb": MODULE.format(name="a"),
                          "b.lb": MODULE.format(name="b"),
                          "c.lb": MODULE.format(name="c"),
                          "child.lb": MODULE.format(name="a:child"),
                          "repo.lb": REPO.replace('(".")', '(".", "*.lb")')})
            buildlog = self.load(*options)
            modules = buildlog.validate("repo:module")[0]
            return sorted(m.fullname for m in modules)

        self.assertEqual(["repo:module"], built("pass"))
        self.assertEqual(["repo:a", "repo:module"], built('module.depends(":a")'))
        # submodules always depend on their parents
        self.assertEqual(["repo:a", "repo:a:child", "repo:b", "repo:module"],
                         built('module.depends("repo:a:child", ":b")'))
        self.assertEqual(["repo:b", "repo:module"], built("pass", "repo:module:needs=b"))
        self.assertEqual(["repo:a", "repo:b", "repo:c", "repo:module"],
                         built('module.depends(":a")', "repo:module:needs=bc"))
        self.assertEqual([True, True, True, False], self.observed()["has"])

        with self.assertRaises(le.LbuildParserCannotResolveDependencyException):
            built('module.depends(":missing")')
        with self.assertRaises(le.LbuildParserCannotResolveDependencyException):
            built('module.depends(":b:missing")')

    def test_should_order_modules(self):
        def module(name, order=None, depends=None):
            return '''
                def init(module):
                    module.name = "{0}"
                    {1}

                def prepare(module, options):
                    {2}
                    return True

                def validate(env):
                    order("validate")

                def build(env):
                    order("build")

                def post_build(env):
                    order("post_build")

                def order(stage):
                    with open("order.txt", "a") as file:
                        file.write(stage + " {0}\\n")
                '''.format(name, "pass" if order is None else "module.order = {}".format(order),
                           "pass" if depends is None else 'module.depends("{}")'.format(depends))

        self.project({"a.lb": module("a", depends=":last"),
                      "b.lb": module("a:b"),
                      "c.lb": module("a:b:c"),
                      "first.lb": module("first", order=-10),
                      "child.lb": module("first:child"),
                      "last.lb": module("last", order="100"),
                      "repo.lb": REPO.replace('(".")', '(".", "*.lb")') + '''
def build(env):
    with open("order.txt", "a") as file:
        file.write("build repo\\n")
'''})
        self.build()
        order = self.read("order.txt").splitlines()

        # Stages are run for all modules before the next one starts.
        # Lower orders are first, then children before their parents and the
        # repository after all of its modules. Dependencies do not matter.
        modules = ["first:child", "first", "a:b:c", "a:b", "a", "last"]
        self.assertEqual(["validate " + m for m in modules] +
                         ["build " + m for m in modules] + ["build repo"] +
                         ["post_build " + m for m in modules], order)

    def test_should_run_legacy_functions(self):
        observed = self.module('''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def pre_build(env):
                observe(pre_build=public(env) == public(env.__class__(env._env)))

            def build(env):
                pass

            def post_build(env, buildlog):
                observe(post_build=[type(buildlog).__name__, buildlog.modules == env.buildlog.modules])
            ''')
        self.assertEqual({"pre_build": True, "post_build": ["BuildLogFacade", True]}, observed)

        with self.assertRaises(le.LbuildAggregateException) as error:
            self.module(MODULE.format(name="module") + '''
def pre_build(env):
    raise PreBuildException("Legacy")
''')
        self.assertIn("Legacy", str(error.exception.exceptions[0]))

    FORMATTED = '''
        def init(node):
            node.name = "{name}"
            node.description = "Description\\nof the node"
            {formatter}

        def prepare(node, options):
            {prepare}

        def build(env):
            pass
        '''
    FORMATTER = '''node.format_description = lambda node, text: "<{}|{}>".format(node.name, text)
            node.format_short_description = lambda node, text: text[:4]'''

    def test_should_format_descriptions(self):
        self.project({
            "repo.lb": self.FORMATTED.format(
                name="repo", formatter=self.FORMATTER, prepare='''
            node.add_modules_recursive(".", "[mo]*.lb")'''),
            "module.lb": self.FORMATTED.format(name="module", formatter="pass", prepare='''
            node.add_option(BooleanOption(name="option", description="Option text"))
            node.add_submodule("child.lb")
            return True'''),
            "child.lb": MODULE.format(name="child"),
            "other.lb": self.FORMATTED.format(name="other", formatter='node.description = ""',
                                              prepare="return True")})
        parser = self.load().parser

        # The formatters of the repository are inherited by everything inside of it
        self.assertEqual("<repo|Description\nof the node>", parser.find_any("repo")[0].description)
        self.assertEqual("Desc", parser.find_any("repo")[0].short_description)
        self.assertEqual("<module|Description\nof the node>",
                         parser.find_module("repo:module").description)
        self.assertEqual("Desc", parser.find_module("repo:module").short_description)
        self.assertEqual("<option|Option text>", parser.find_option("repo:module:option").description)
        self.assertEqual("<child|>", parser.find_module("repo:module:child").description)
        self.assertEqual("<other|>", parser.find_module("repo:other").description)
        self.assertEqual("", parser.find_module("repo:other").short_description)

    @unittest.expectedFailure
    def test_should_format_descriptions_of_module(self):
        # FIXME: the formatters set by a module are ignored
        self.project({"module.lb": self.FORMATTED.format(name="module", formatter=self.FORMATTER,
                                                          prepare="return True")})
        parser = self.load().parser
        self.assertEqual("<module|Description\nof the node>",
                         parser.find_module("repo:module").description)

    def test_should_describe_without_formatter(self):
        self.project({"module.lb": self.FORMATTED.format(name="module", formatter="pass",
                                                          prepare="return True"),
                      "other.lb": self.FORMATTED.format(name="other", prepare="return True",
                                                         formatter='node.description = ""'),
                      "repo.lb": REPO.replace('(".")', '(".", "*.lb")')})
        parser = self.load().parser

        self.assertEqual(">> repo:module  [Module]\n\nDescription\nof the node",
                         parser.find_module("repo:module").description)
        self.assertEqual("Description", parser.find_module("repo:module").short_description)
        self.assertEqual(">> repo:other  [Module]", parser.find_module("repo:other").description)
        self.assertEqual("", parser.find_module("repo:other").short_description)

    def test_should_forward_exception_in_formatter(self):
        self.project({"repo.lb": self.FORMATTED.format(
            name="repo", formatter="node.format_description = lambda node, text: 1 / 0",
            prepare='node.add_modules_recursive(".")'), "module.lb": MODULE.format(name="module")})
        parser = self.load().parser
        with self.assertRaises(le.LbuildForwardException):
            parser.find_module("repo:module").description


class OptionFacadeTest(FacadeTestCase):

    SOURCE = '''
        import enum

        class Level(enum.Enum):
            LOW = 1
            HIGH = 2

        def no_spaces(value):
            if " " in value:
                raise ValueError("No spaces allowed!")

        def init(module):
            module.name = "module"

        def prepare(module, options):
            module.add_option(StringOption(name="string", description="", default="text",
                                           validate=no_spaces, transform=lambda v: v.upper()))
            module.add_option(BooleanOption(name="boolean", description="",
                                            transform=lambda v: {{"on": True, "off": False}}.get(v, v)))
            module.add_option(NumericOption(name="numeric", description="", minimum="-1Ki",
                                            maximum=0x10, default=2))
            module.add_option(NumericOption(name="float", description="", default=1.5))
            module.add_option(EnumerationOption(name="enum", description="", enumeration=Level,
                                                default=Level.LOW))
            module.add_option(EnumerationOption(name="range", description="", enumeration=range(3),
                                                default=1))
            module.add_option(EnumerationOption(name="dict", description="", default="one",
                                                enumeration={{"one": 1, "list": [2, 3]}}))
            module.add_option(PathOption(name="relative", description="", default="sub/file"))
            module.add_option(PathOption(name="absolute", description="", default="sub/file",
                                         absolute=True))
            module.add_option(PathOption(name="empty", description="", default="", empty_ok=True))
            module.add_set_option(BooleanOption(name="booleans", description=""))
            module.add_set_option(PathOption(name="paths", description="", absolute=True),
                                  default=["a", "b"])
            module.add_list_option(EnumerationOption(name="levels", description="",
                                                     enumeration=Level), default=Level.HIGH)
            module.add_option(SetOption(name="legacy", description="", enumeration=[1, 2, 3],
                                        default=[1, 2]))
            {prepare}
            return True

        def build(env):
            names = ["string", "boolean", "numeric", "float", "enum", "range", "dict", "relative",
                     "absolute", "empty", "booleans", "paths", "levels", "legacy"]
            observe(**{{name: env[name] for name in names}})
        '''

    def options(self, *options, prepare="pass"):
        return self.module(self.SOURCE.format(prepare=prepare), *options)

    def test_should_convert_defaults(self):
        self.assertEqual({
            "string": "TEXT", "boolean": False, "numeric": 2, "float": 1.5, "enum": 1, "range": 1,
            "dict": 1, "relative": "sub/file", "absolute": join(self.root, "sub/file"),
            "empty": "", "booleans": [], "paths": [join(self.root, "a"), join(self.root, "b")],
            "levels": [2], "legacy": [1, 2],
        }, self.options())

    def test_should_convert_inputs(self):
        self.assertEqual({
            "string": "OTHER", "boolean": True, "numeric": -1024, "float": 2500.0, "enum": 2,
            "range": 2, "dict": [2, 3], "relative": "../file",
            "absolute": join(self.root, "x/file"), "empty": "not/empty",
            "booleans": [True, False], "paths": [join(self.root, "c")], "levels": [1, 2, 1],
            "legacy": [3, 1],
        }, self.options("repo:module:string=other", "repo:module:boolean=on",
                        "repo:module:numeric=-1Ki", "repo:module:float=2.5K",
                        "repo:module:enum=Level.HIGH", "repo:module:range=2", "repo:module:dict=list",
                        "repo:module:relative=../file", "repo:module:absolute=x/file",
                        "repo:module:empty=not/empty", "repo:module:booleans=yes,no,yes",
                        "repo:module:paths=c", "repo:module:levels=Level.LOW, Level.HIGH,Level.LOW",
                        "repo:module:legacy=3,1,3"))

    @unittest.expectedFailure
    def test_should_convert_enum_names(self):
        # FIXME: the members of an enum class are called `Level.HIGH` instead
        self.assertEqual(2, self.options("repo:module:enum=HIGH")["enum"])

    def test_should_evaluate_numeric_expressions(self):
        for value, result in (("1+2", 3), ("2**4", 16), ("0x10", 16), ("1Mi", 1048576),
                              ("-8", -8)):
            self.assertEqual(result, self.options("repo:module:float=" + value)["float"], value)

    def test_should_reject_inputs(self):
        for option in ("string=with space", "boolean=2", "numeric=17", "numeric=-1025",
                       "numeric=text", "enum=MEDIUM", "enum=1", "range=3", "dict=two",
                       "relative=", "booleans=yes,maybe", "levels=LOW,NONE", "legacy=4"):
            with self.assertRaises(le.LbuildParserOptionInvalidException, msg=option):
                self.options("repo:module:" + option)

    def test_should_reject_invalid_options(self):
        for option in ('NumericOption(name="o", description="", minimum=2, maximum=1)',
                       'NumericOption(name="o", description="", minimum="low")',
                       'NumericOption(name="o", description="", maximum="high")',
                       'EnumerationOption(name="o", description="", enumeration={1: 2})',
                       'EnumerationOption(name="o", description="", enumeration=[1], default=2)',
                       'BooleanOption(name="o", description="", default="maybe")',
                       'PathOption(name="o", description="", default="")'):
            with self.assertRaises(le.LbuildOptionException, msg=option):
                self.options(prepare="module.add_option({})".format(option))

    @unittest.expectedFailure
    def test_should_reject_set_of_strings(self):
        # FIXME: raises an AttributeError while describing the incomplete option
        with self.assertRaises(le.LbuildOptionException):
            self.options(prepare='module.add_set_option(StringOption(name="o", description=""))')

    @unittest.expectedFailure
    def test_should_reject_invalid_numeric_default(self):
        # FIXME: raises an AttributeError while describing the incomplete option
        with self.assertRaises(le.LbuildOptionException):
            self.options(prepare='module.add_option(NumericOption(name="o", description="", '
                                 'default="text"))')

    @unittest.expectedFailure
    def test_should_reject_invalid_enumeration(self):
        # FIXME: raises an AttributeError while describing the incomplete option
        with self.assertRaises(le.LbuildOptionException):
            self.options(prepare='module.add_option(EnumerationOption(name="o", description="", '
                                 'enumeration=[1, 1]))')

    @unittest.expectedFailure
    def test_should_check_range_of_numeric_default(self):
        # FIXME: only inputs are checked against the limits
        with self.assertRaises(le.LbuildOptionException):
            self.options(prepare='module.add_option(NumericOption(name="o", description="", '
                                 'minimum=1, default=0))')

    @unittest.expectedFailure
    def test_should_use_default_of_option_in_set(self):
        # FIXME: only the default passed to `add_set_option()` is used
        observed = self.options(prepare='module.add_set_option(NumericOption('
                                        'name="string", description="", default=3))')
        self.assertEqual([3], observed["string"])

    def test_should_require_option_without_default(self):
        prepare = 'module.add_option(StringOption(name="required", description=""))'
        with self.assertRaises(le.LbuildOptionRequiredInputsException):
            self.options(prepare=prepare)
        self.options("repo:module:required=now", prepare=prepare)

    def test_should_resolve_option_names(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_option(NumericOption(name="value", description="", default=1))
                module.add_option(NumericOption(name="dotted.name", description="", default=2))
                module.add_submodule("child.lb")
                return True

            def build(env):
                observe(module=[env["value"], env["::value"], env[":module:value"],
                                env["repo:module:value"], env["repo::value"], env["dotted.name"],
                                env[":module:child:value"], env["repo:value"], env[":value"],
                                env.get("value"), env.get(":child:value"), env.get("missing", 5),
                                env.has_option("value"), env.has_option(":child:value"),
                                env.has_option(":other:value")])
            ''', "child.lb": '''
            def init(module):
                module.name = "child"

            def prepare(module, options):
                module.add_option(NumericOption(name="value", description="", default=3))
                return True

            def build(env):
                observe(child=[env["value"], env[":::value"], env["::value"], env[":module:value"],
                               env["::child:value"], env[":value"]])
            ''', "repo.lb": '''
            def init(repo):
                repo.name = "repo"
                repo.add_option(NumericOption(name="value", description="", default=4))

            def prepare(repo, options):
                repo.add_modules_recursive(".")

            def build(env):
                observe(repo=[env["value"], env[":value"], env[":module:value"],
                              env["repo:module:child:value"], env.has_option("module:value")])
            '''})
        self.build()

        self.assertEqual({
            "module": [1, 1, 1, 1, 1, 2, 3, 4, 4, 1, None, 5, True, False, False],
            "child": [3, 3, 1, 1, 3, 4],
            "repo": [4, 4, 1, 3, False],
        }, self.observed())

    def test_should_not_resolve_unknown_or_ambiguous_names(self):
        for access in ('env["missing"]', 'env[":missing:value"]', 'env["*"]', 'env["dotted"]',
                       'env[":module"]', 'env.query("value")'):
            with self.assertRaises(le.LbuildResolverException, msg=access):
                self.module('''
                    def init(module):
                        module.name = "module"

                    def prepare(module, options):
                        module.add_option(NumericOption(name="value", description="", default=1))
                        module.add_option(NumericOption(name="dotted.name", description="",
                                                        default=2))
                        return True

                    def build(env):
                        {}
                    '''.format(access))

    def test_should_not_resolve_options_of_unselected_modules(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                observe(has=[env.has_module(":other"), env.has_option(":other:value"),
                             env.get(":other:value", "default"), env.has_query(":other:query"),
                             env.has_collector(":other:collector")])
                env[":other:value"]
            ''', "other.lb": '''
            def init(module):
                module.name = "other"

            def prepare(module, options):
                module.add_option(NumericOption(name="value", description="", default=1))
                module.add_query(Query(name="query", function=lambda: None))
                module.add_collector(StringCollector(name="collector", description=""))
                return True

            def build(env):
                pass
            ''', "repo.lb": REPO.replace('(".")', '(".", "*.lb")')})

        with self.assertRaises(le.LbuildResolverSearchException) as error:
            self.build(modules="repo:module")
        self.assertIn("is not selected!", str(error.exception))
        # A collector can be filled without its module being built
        self.assertEqual({"has": [False, False, "default", False, True]}, self.observed())


class EnvironmentFacadeTest(FacadeTestCase):

    VALIDATE = ["cwdoutpath", "cwdpath", "filter", "get", "get_option", "has_collector",
                "has_filter", "has_module", "has_option", "has_query", "localpath", "log", "query",
                "relcwdoutpath", "repopath"]
    COMMON = ["copy", "extract", "generated_local_files", "get_generated_local_files",
              "ignore_files", "ignore_paths", "ignore_patterns", "outbasepath", "outpath",
              "real_outpath", "relative_outpath", "reloutpath", "substitutions", "template"]
    BUILD = sorted(VALIDATE + COMMON + ["add_metadata", "append_metadata",
                                        "append_metadata_unique", "collect"])
    POST_BUILD = sorted(VALIDATE + COMMON + ["buildlog", "collector", "collector_values"])

    def test_should_provide_interface_for_stage(self):
        observed = self.module('''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                observe(prepare=public(options))
                return True

            def validate(env):
                observe(validate=public(env))

            def build(env):
                observe(build=public(env))

            def post_build(env):
                observe(post_build=public(env), buildlog=public(env.buildlog),
                        operation=public(env.buildlog.operations[0]) if env.buildlog.operations
                                  else None)
            ''')

        self.assertEqual({"prepare": ["get"], "validate": self.VALIDATE, "build": self.BUILD,
                          "post_build": self.POST_BUILD,
                          "buildlog": ["get_operations_per_module", "metadata", "module_metadata",
                                       "modules", "operation_metadata", "operations",
                                       "operations_per_module", "outpath", "repo_metadata",
                                       "repositories"],
                          "operation": None}, observed)

    def test_should_relocate_paths(self):
        self.project({"sub/module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def paths(env):
                return [env.localpath(), env.localpath("a", "b"), env.repopath("a", "b"),
                        env.repopath(".."), env.cwdpath("a", "b"), env.cwdoutpath("a", "b"),
                        env.relcwdoutpath("a", "b"), env.relcwdoutpath("../a")]

            def validate(env):
                observe(validate=paths(env))

            def build(env):
                env.outbasepath = "base"
                observe(build=paths(env), out=[
                    env.outbasepath, env.real_outpath("a/b"), env.real_outpath("a", basepath="."),
                    env.real_outpath("a", basepath="other"), env.relative_outpath("a/b"),
                    env.relative_outpath("a/b", "a"), env.relative_outpath("a/b", "c/d")])

            def post_build(env):
                observe(post_build=paths(env), post_out=[
                    env.outbasepath, env.real_outpath("a"), env.relative_outpath("a", "b")])
            '''})
        self.build()
        observed = self.observed()

        out = join(self.root, "out")
        paths = [join(self.root, "sub"), join(self.root, "sub/a/b"), "sub/a/b", ".",
                 join(self.root, "a/b"), join(out, "a/b"), "out/a/b", "a"]
        self.assertEqual(paths, observed["validate"])
        # the base path is only used for generating files
        self.assertEqual(paths, observed["build"])
        self.assertEqual(paths, observed["post_build"])
        self.assertEqual(["base", join(out, "base/a/b"), join(out, "./a"), join(out, "other/a"),
                          "a/b", "b", "../../a/b"], observed["out"])
        # every stage starts without a base path, but keeps it
        self.assertEqual(["base", join(out, "base/a"), "../a"], observed["post_out"])

    def test_should_copy(self):
        self.project({"sub/module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                ops = env.copy("file.txt")
                observe(operation=[[op.module, op.repository, op.filename, op.has_filename]
                                   for op in ops])
                env.copy("file.txt", "renamed.txt")
                env.copy("file.txt", dest="deep/er/file.txt")
                env.copy("../other/file.txt", "other.txt")
                env.copy(env.localpath("folder/a.txt"), env.cwdpath("absolute.txt"))
                env.outbasepath = "base"
                observe(folder=sorted(op.filename for op in env.copy("folder")))
                env.copy("folder", "ignored", ignore=env.ignore_files("*.txt", "empty"))
                env.copy("folder", "paths", ignore=env.ignore_paths("*/nested/*.txt"))
                env.copy("folder", "custom", ignore=lambda path, files: [f for f in files if "a" in f])
                env.copy("folder/", "slash/")
                env.copy(".", "all")
                observe(local=sorted(env.generated_local_files()),
                        filtered=env.generated_local_files(lambda path: path.endswith("b.dat")),
                        named=env.generated_local_files(filterfunc=lambda path: "renamed" in path))
            ''', "repo.lb": REPO_SINGLE.format("sub/module.lb"),
                      "sub/file.txt": "file", "other/file.txt": "other", "sub/folder/a.txt": "a",
                      "sub/folder/nested/b.txt": "b", "sub/folder/nested/b.dat": "dat",
                      "sub/folder/.git/config": "", "sub/folder/.DS_Store": "",
                      "sub/folder/__pycache__/a.pyc": "", "sub/folder/repo.lb": "",
                      "sub/folder/module.lb": "", "sub/folder/nested/c.pyc": ""})
        self.build()
        observed = self.observed()

        self.assertEqual([["repo:module", "repo", "file.txt", True]], observed["operation"])
        folder = ["a.txt", "nested/b.dat", "nested/b.txt"]
        self.assertEqual([join("base/folder", f) for f in folder], observed["folder"])
        self.assertEqual(sorted(
            ["file.txt", "renamed.txt", "deep/er/file.txt", "other.txt"] +
            [join("base", name, f) for name in ("folder", "slash", "all/folder") for f in folder] +
            ["base/ignored/nested/b.dat", "base/paths/a.txt", "base/paths/nested/b.dat",
             "base/custom/nested/b.txt", "base/all/file.txt"]), self.files())
        self.assertEqual("other", self.read("out/other.txt"))
        self.assertEqual("a", self.read("absolute.txt"))
        # relative to the base path at the time of the call
        self.assertIn("../renamed.txt", observed["local"])
        self.assertIn("folder/a.txt", observed["local"])
        self.assertIn("../../absolute.txt", observed["local"])
        self.assertEqual(len(self.files()) + 1, len(observed["local"]))
        self.assertEqual(["all/folder/nested/b.dat", "folder/nested/b.dat",
                          "ignored/nested/b.dat", "paths/nested/b.dat", "slash/nested/b.dat"],
                         sorted(observed["filtered"]))
        self.assertEqual(["../renamed.txt"], observed["named"])

    def test_should_copy_with_symlinks(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                env.copy("file.txt")
                env.copy("folder")
            ''', "file.txt": "", "folder/file.txt": ""})
        builder = self.load()
        builder.build(modules="repo:**", use_symlinks=True)
        builder = self.load()
        builder.build(modules="repo:**", use_symlinks=True)

        self.assertEqual(join(self.root, "file.txt"), os.path.realpath("out/file.txt"))
        self.assertTrue(os.path.islink("out/folder/file.txt"))
        self.assertFalse(os.path.islink("out/folder"))

    def test_should_extract(self):
        self.project({"sub/module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                for archive in ("archive.zip", "archive.tar"):
                    env.outbasepath = archive[-3:]
                    ops = env.extract(archive)
                    observe(**{archive: sorted(op.filename for op in ops)})
                    env.extract(archive, "folder/", "renamed")
                    env.extract(archive, src="folder/nested/b.txt", dest="b.txt")
                    env.extract(archive, src="file.txt", dest="single/renamed.txt")
                    # the names of folders in an archive end with a slash
                    env.extract(archive, dest="ignored", ignore=env.ignore_files("folder*"))
                    env.extract("../sub/" + archive, "folder/nested/", env.cwdpath(archive + ".d"))
            '''})
        members = ("file.txt", "folder/", "folder/a.txt", "folder/module.lb", "folder/nested/",
                   "folder/nested/b.txt")
        for name in members:
            os.makedirs(os.path.dirname(join("content", name)), exist_ok=True)
            if not name.endswith("/"):
                with open(join("content", name), "w") as file:
                    file.write(name)
        with zipfile.ZipFile("sub/archive.zip", "w") as archive:
            for name in members:
                archive.write(join("content", name), name)
        with tarfile.TarFile("sub/archive.tar", "w") as archive:
            for name in members:
                archive.add(join("content", name), name.rstrip("/"), recursive=False)
        shutil.rmtree("content")
        self.build()

        files = ["file.txt", "folder/a.txt", "folder/nested/b.txt"]
        for kind in ("zip", "tar"):
            self.assertEqual([join(kind, f) for f in files],
                             self.observed()["archive." + kind])
            self.assertEqual(sorted(files + ["b.txt", "ignored/file.txt", "renamed/a.txt",
                                             "renamed/nested/b.txt", "single/renamed.txt"]),
                             self.files(join("out", kind)))
            self.assertEqual("folder/nested/b.txt", self.read(join("out", kind, files[2])))
            self.assertEqual(["b.txt"], self.files("archive.{}.d".format(kind)))

    def test_should_render_template(self):
        self.project({"sub/module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_option(NumericOption(name="option", description="", default=7))
                module.add_collector(StringCollector(name="collector", description=""))
                return True

            def build(env):
                env.collect("collector", "x", "y")
                ops = env.template("file.txt.in")
                observe(operation=[[op.module, op.repository, op.filename, op.has_filename]
                                   for op in ops])
                env.template("plain.txt")
                env.template("multi.in.txt.in")
                env.template("file.txt.in", "renamed.txt", substitutions={"value": "local"})
                env.template(env.localpath("file.txt.in"), env.cwdpath("absolute.txt"))
                env.substitutions = {"value": "global"}
                env.template("file.txt.in", "global.txt")
                env.substitutions["value"] = "updated"
                env.template("file.txt.in", dest="updated.txt")
                # FIXME: the environment substitutions overwrite the local ones
                env.template("file.txt.in", "both.txt", substitutions={"value": "local"})
                env.outbasepath = "base"
                env.template("nested/include.txt.in", "include.txt",
                             filters={"shout": lambda text: text.upper() + "!"})
                env.template("nested/include.txt.in", "other_filter.txt",
                             filters={"shout": lambda text: text.upper() + "?"})
                env.template("nested/globals.txt.in",
                             substitutions={"time": "now", "none": None})
            ''',
                      "sub/file.txt.in": "{{ value | default('undefined') }}",
                      "sub/plain.txt": "{{ 1 + 1 }}",
                      "sub/multi.in.txt.in": "%% if True\nline statement\n%% endif\n%# comment\nend",
                      "sub/nested/include.txt.in":
                          "{% include 'part.in' %}|{% include '../file.txt.in' %}|"
                          "{% include '../../shared/part.in' %}|{{ 'filter' | shout }}",
                      "sub/nested/part.in": "part of {{ value }}",
                      "shared/part.in": "shared",
                      "sub/nested/globals.txt.in":
                          "{{ options['option'] }} {{ options[':module:option'] }} "
                          "{{ collector_values['collector'] | join(',') }} "
                          "{{ collector_values[':module:collector'] | length }} "
                          "{{ collector_values.get('missing') }} {{ time }} "
                          "{% do [].append(1) %}{{ none is none }}"})
        self.build()

        self.assertEqual([["repo:module", "repo", "file.txt", True]], self.observed()["operation"])
        self.assertEqual({
            "file.txt": "undefined", "plain.txt": "2", "multi.in.txt": "line statement\n\nend",
            "renamed.txt": "local", "global.txt": "global", "updated.txt": "updated",
            "both.txt": "updated",
            "base/include.txt": "part of updated|updated|shared|FILTER!",
            "base/other_filter.txt": "part of updated|updated|shared|FILTER?",
            "base/nested/globals.txt": "7 7 x,y 2 [] now True",
        }, {name: self.read(join("out", name)) for name in self.files()})
        self.assertEqual("undefined", self.read("absolute.txt"))

    def test_should_fail_to_generate_files(self):
        def build(call, **files):
            self.project(dict({"sub/module.lb": '''
                def init(module):
                    module.name = "module"

                def prepare(module, options):
                    return True

                def build(env):
                    {}
                '''.format(call), "sub/file.txt": "", "outside.txt": "",
                               "sub/broken.txt.in": "{{ undefined }}",
                               "sub/syntax.txt.in": "{% if %}"}, **files))
            self.build()

        for function in ("copy", "template", "extract"):
            with self.assertRaises(le.LbuildEnvironmentFileNotFoundException, msg=function):
                build('env.{}("missing.txt")'.format(function))
            with self.assertRaises(le.LbuildEnvironmentFileOutsideRepositoryException, msg=function):
                build('env.{}("../../outside.txt")'.format(function), **{"../outside.txt": ""})
            with self.assertRaises(le.LbuildBuildlogOverwritingFileException, msg=function):
                build('env.copy("file.txt", "same"); env.{}("{}", {}"same")'.format(
                    function, "archive.zip" if function == "extract" else "file.txt",
                    '"file.txt", ' if function == "extract" else ""),
                      **{"sub/archive.zip": self.archive()})

        with self.assertRaises(le.LbuildEnvironmentArchiveNoFileException):
            build('env.extract("archive.zip", "missing.txt")', **{"sub/archive.zip": self.archive()})
        with self.assertRaises(le.LbuildEnvironmentTemplateException) as error:
            build('env.template("broken.txt.in")')
        self.assertIn("'undefined' is undefined", str(error.exception))
        with self.assertRaises(le.LbuildEnvironmentTemplateException):
            build('env.template("syntax.txt.in")')
        with self.assertRaises(le.LbuildForwardException) as error:
            build('raise NotImplementedError("in build")')
        self.assertIn("in build", str(error.exception))

    def test_should_not_write_files_when_simulating(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                env.template("file.txt")
                env.extract("archive.zip", dest="extracted")

            def post_build(env):
                observe(files=sorted(op.filename for op in env.buildlog))
            ''', "file.txt": "", "archive.zip": self.archive()})
        buildlog = self.load().build(modules="repo:**", simulate=True)

        self.assertEqual({"files": ["extracted/file.txt", "file.txt"]}, self.observed())
        self.assertEqual(2, len(buildlog.operations))
        self.assertFalse(os.path.exists("out/file.txt"))
        self.assertFalse(os.path.exists("out/extracted/file.txt"))

    def test_should_log(self):
        self.project({"sub/module.lb": '''
            def init(module):
                module.name = "module:child"

            def prepare(module, options):
                return True

            def validate(env):
                env.log.debug("Debug %s", 1)
                env.log.info("Info")
                env.log.warning("Warning")
                env.log.error("Error")
                env.log.critical("Critical")

            def build(env):
                observe(name=env.log.name)
            ''', "module.lb": MODULE.format(name="module")})
        with self.assertLogs("user", logging.DEBUG) as logs:
            self.build()

        self.assertEqual(["DEBUG:user.repo.module.child:Debug 1",
                          "INFO:user.repo.module.child:Info",
                          "WARNING:user.repo.module.child:Warning",
                          "ERROR:user.repo.module.child:Error",
                          "CRITICAL:user.repo.module.child:Critical"], logs.output)
        self.assertEqual({"name": "user.repo.module.child"}, self.observed())

    def test_should_validate(self):
        def validate(body, *options):
            self.project({"module.lb": '''
                def init(module):
                    module.name = "module"

                def prepare(module, options):
                    module.add_option(BooleanOption(name="fail", description="", default=True))
                    return True

                def validate(env):
                    {}

                def build(env):
                    observe(built=True)

                def post_build(env):
                    observe(post_built=True)
                '''.format(body)})
            return self.load(*options)

        builder = validate('raise ValidateException("Reason")')
        with self.assertRaises(le.LbuildAggregateException) as error:
            builder.validate("repo:module")
        self.assertIn("Reason", str(error.exception))
        self.assertIn("module.lb", str(error.exception))
        with self.assertRaises(le.LbuildAggregateException):
            builder.build(modules="repo:module")
        self.assertFalse(os.path.exists("observed.json"))

        # the build steps are only simulated to find problems in them
        builder = validate('if env["fail"]: raise ValidateException("Reason")', "repo:module:fail=no")
        modules, _ = builder.validate("repo:module")
        self.assertEqual(["repo:module"], [m.fullname for m in modules])
        self.assertEqual({"built": True, "post_built": True}, self.observed())
        self.assertEqual([], self.files())

        os.remove("observed.json")
        builder = validate("pass")
        builder.validate("repo:module", complete=False)
        self.assertFalse(os.path.exists("observed.json"))


class CollectorFacadeTest(FacadeTestCase):

    COLLECTORS = '''
        import enum

        class Level(enum.Enum):
            LOW = 1
            HIGH = 2

        def no_spaces(value):
            if " " in value:
                raise ValueError("No spaces allowed!")

        def init(module):
            module.name = "module"

        def prepare(module, options):
            module.add_collector(StringCollector(name="string", description="Strings",
                                                 validate=no_spaces))
            module.add_collector(PathCollector(name="path", description=""))
            module.add_collector(PathCollector(name="absolute", description="", absolute=True,
                                               empty_ok=True))
            module.add_collector(BooleanCollector(name="boolean", description=""))
            module.add_collector(NumericCollector(name="numeric", description="", minimum=0,
                                                  maximum=10))
            module.add_collector(EnumerationCollector(name="enum", description="",
                                                      enumeration=Level))
            module.add_collector(CallableCollector(name="callable", description=""))
            return True
        '''

    def test_should_collect_all_types(self):
        observed = self.module(self.COLLECTORS + '''
        def build(env):
            env.collect("string", "a", "b")
            env.collect("string", "a")
            env.collect("string")
            env.collect(":module:path", "a/b", "../c")
            env.collect("repo:module:absolute", "a", "")
            env.collect("::boolean", True, "no", 1, "yes")
            env.collect("numeric", 1, "2", "2*4", 1.5)
            env.collect("enum", Level.HIGH, Level.LOW, "Level.HIGH")
            env.collect("callable", len, int)

        def post_build(env):
            names = ["string", "path", "absolute", "boolean", "numeric", "enum"]
            observe(values={name: env.collector_values(name) for name in names},
                    all={name: env.collector_values(name, unique=False) for name in names},
                    callables=[f.__name__ for f in env.collector_values("callable")])
        ''')

        self.assertEqual({"string": ["a", "b"], "path": ["a/b", "../c"],
                          "absolute": [join(self.root, "a"), ""], "boolean": [True, False],
                          "numeric": [1, 2, 8, 1.5], "enum": [2, 1]}, observed["values"])
        self.assertEqual({"string": ["a", "b", "a"], "path": ["a/b", "../c"],
                          "absolute": [join(self.root, "a"), ""],
                          "boolean": [True, False, True, True], "numeric": [1, 2, 8, 1.5],
                          "enum": [2, 1, 2]}, observed["all"])
        self.assertEqual(["len", "int"], observed["callables"])

    def test_should_reject_values(self):
        for call in ('"string", "a b"', '"path", ""', '"boolean", "maybe"', '"numeric", 11',
                     '"numeric", "text"', '"enum", "MEDIUM"', '"callable", 1'):
            with self.assertRaises(le.LbuildEnvironmentCollectException, msg=call) as error:
                self.module(self.COLLECTORS + '''
        def build(env):
            env.collect({})
        '''.format(call))
            self.assertIn("repo:module", str(error.exception))

        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.module(self.COLLECTORS + '''
        def build(env):
            env.collect("missing", 1)
        ''')

    def test_should_filter_values_by_scope(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_collector(StringCollector(name="flags", description=""))
                return True

            def build(env):
                env.collect("flags", "-module", "-shared")
                env.outbasepath = "sub"
                operations = env.copy("folder")
                env.collect("flags", "-file", "-shared", operations=operations)
                env.collect("flags", "-none", operations=[])

            def post_build(env):
                scopes = [[scope.module, scope.repository, scope.filename, scope.has_filename, values]
                          for scope, values in env.collector("flags").items()]
                collector = env.collector("flags")
                observe(interface=public(collector),
                        scopes=sorted(scopes, key=str),
                        operations=sorted(str(scope.filename) for scope in collector.operations()),
                        values=sorted(env.collector_values("flags")),
                        all=sorted(env.collector_values("flags", unique=False)),
                        files=sorted(env.collector_values(
                            "flags", filterfunc=lambda scope: scope.has_filename)),
                        child=sorted(env.collector_values(
                            "flags", filterfunc=lambda scope: scope.module == "repo:module:child")),
                        other=sorted(env.collector_values(
                            "flags", filterfunc=lambda scope: scope.repository == "other")),
                        default=[env.collector_values("flags", "default"),
                                 env.collector_values("flags", default="default",
                                                      filterfunc=lambda scope: False),
                                 env.collector_values("missing", default="default"),
                                 env.collector_values("missing", default=[1, 2]),
                                 env.collector_values("flags", filterfunc=lambda scope: False)],
                        has=[env.has_collector("flags"), env.has_collector("missing"),
                             env.has_collector(":module:flags")])
            ''', "child.lb": '''
            def init(module):
                module.name = "module:child"

            def prepare(module, options):
                return True

            def build(env):
                env.collect("::flags", "-child", "-shared")
                observe(build_has=[env.has_collector("::flags"), env.has_collector("flags")])
            ''', "repo.lb": REPO.replace('(".")', '(".", "*.lb")') + '''
def build(env):
    env.collect(":module:flags", "-repo")
''', "folder/a.c": "", "folder/b.c": ""})
        self.load(collectors=["repo:module:flags=-config"]).build(modules="repo:**")
        observed = self.observed()

        self.assertEqual(["items", "operations", "values"], observed["interface"])
        self.assertEqual([["repo", "repo", None, False, ["-config"]],
                          ["repo", "repo", None, False, ["-repo"]],
                          ["repo:module", "repo", "sub/folder/a.c", True, ["-file", "-shared"]],
                          ["repo:module", "repo", "sub/folder/b.c", True, ["-file", "-shared"]],
                          ["repo:module", "repo", None, False, ["-module", "-shared"]],
                          ["repo:module:child", "repo", None, False, ["-child", "-shared"]]],
                         observed["scopes"])
        self.assertEqual(["None", "None", "None", "None", "sub/folder/a.c", "sub/folder/b.c"],
                         observed["operations"])
        self.assertEqual(["-child", "-config", "-file", "-module", "-repo", "-shared"],
                         observed["values"])
        self.assertEqual(["-child", "-config", "-file", "-file", "-module", "-repo", "-shared",
                          "-shared", "-shared", "-shared"], observed["all"])
        self.assertEqual(["-file", "-shared"], observed["files"])
        self.assertEqual(["-child", "-shared"], observed["child"])
        self.assertEqual([], observed["other"])
        self.assertEqual(6, len(observed["default"][0]))
        self.assertEqual([["default"], ["default"], [1, 2], []], observed["default"][1:])
        self.assertEqual([True, False, True], observed["has"])
        self.assertEqual([True, False], observed["build_has"])

    @unittest.expectedFailure
    def test_should_read_values_of_collector(self):
        # FIXME: the arguments are passed on in the wrong order
        observed = self.module(self.COLLECTORS + '''
        def build(env):
            env.collect("string", "a", "b", "a")

        def post_build(env):
            observe(values=env.collector("string").values(),
                    all=env.collector("string").values(unique=False))
        ''')
        self.assertEqual({"values": ["a", "b"], "all": ["a", "b", "a"]}, observed)

    def test_should_not_read_unknown_collector(self):
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.module(MODULE.format(name="module") + '''
def post_build(env):
    env.collector_values("missing")
''')
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.module(MODULE.format(name="module") + '''
def post_build(env):
    env.collector("missing")
''')


class QueryFacadeTest(FacadeTestCase):

    def test_should_query(self):
        self.project({"module.lb": '''
            calls = []

            def expensive(env):
                """Is only computed once."""
                calls.append(env["value"])
                return {"value": env["value"], "stage": type(env).__name__, "calls": len(calls)}

            def plain(first, second=2):
                return [first, second]

            def init(module):
                module.name = "module"

            def prepare(module, options):
                module.add_option(NumericOption(name="value", description="", default=1))
                module.add_query(EnvironmentQuery(name="expensive", factory=expensive))
                module.add_query(Query(function=plain))
                module.add_query(Query(name="renamed", function=plain))
                module.add_query(Query(name="constant", function=lambda: 42))
                return True

            def validate(env):
                observe(validate=[env.query("expensive"), env.query("plain")(1),
                                  env.query(":module:renamed")(1, second=3),
                                  env.query("repo:module:constant")(),
                                  env.has_query("expensive"), env.has_query(":module:plain"),
                                  env.has_query("missing"), env.has_query("value")])

            def build(env):
                observe(build=env.query("expensive"))

            def post_build(env):
                observe(post_build=env.query("expensive"))
            ''', "other.lb": '''
            def init(module):
                module.name = "other"

            def prepare(module, options):
                module.add_option(NumericOption(name="value", description="", default=2))
                module.depends(":module")
                return True

            def build(env):
                observe(other=[env.query(":module:expensive"), env.query(":module:plain")(5),
                               env.has_query("expensive")])
            ''', "repo.lb": REPO.replace('(".")', '(".", "*.lb")')})
        self.build()
        observed = self.observed()

        # The result is computed in the stage and module of the first caller
        expensive = {"value": 1, "stage": "EnvironmentValidateFacade", "calls": 1}
        self.assertEqual([expensive, [1, 2], [1, 3], 42, True, True, False, False],
                         observed["validate"])
        self.assertEqual(expensive, observed["build"])
        self.assertEqual(expensive, observed["post_build"])
        self.assertEqual([expensive, [5, 2], False], observed["other"])

    def test_should_query_with_default(self):
        with self.assertWarns(DeprecationWarning):
            observed = self.module('''
                def init(module):
                    module.name = "module"

                def prepare(module, options):
                    module.add_query(Query(name="query", function=lambda: 1))
                    return True

                def build(env):
                    observe(default=[env.query("missing", "default"), env.query(":other:query", {}),
                                     env.query("query", 2)()])
                ''')
        self.assertEqual({"default": ["default", {}, 1]}, observed)

    def test_should_not_query_unknown(self):
        with self.assertRaises(le.LbuildResolverNoMatchException):
            self.module(MODULE.format(name="module").replace("pass", 'env.query("missing")'))

    def test_should_reject_invalid_queries(self):
        for query in ('Query(function=lambda: None)', 'Query(name="q", function=5)',
                      'EnvironmentQuery(name="q", factory=lambda: None)',
                      'EnvironmentQuery(name="q", factory=lambda env, other: None)'):
            with self.assertRaises(le.LbuildQueryConstructionException, msg=query):
                self.module(MODULE.format(name="module").replace(
                    "return True", "module.add_query({})\n    return True".format(query)))


class BuildlogFacadeTest(FacadeTestCase):

    def test_should_provide_operations(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                observe(build=hasattr(env, "buildlog"))
                env.outbasepath = "repo/module"
                env.copy("file.txt")
                env.template("file.txt", "template.txt")

            def post_build(env):
                log = env.buildlog
                observe(repositories=sorted(log.repositories),
                        modules=log.modules,
                        operations=[[op.module, op.repository, op.filename, op.has_filename]
                                    for op in log.operations],
                        iterated=[op.filename for op in log],
                        per_module={name: [op.local_filename_out() for op in
                                           log.operations_per_module(name)]
                                    for name in ("repo:module", "repo:module:child", "repo",
                                                 "other", "missing")},
                        interface=public(log.operations[0]))
                # Files generated now are added to the log
                env.copy("file.txt", "late.txt")
                observe(late="repo/module/late.txt" in [op.filename for op in log])
            ''', "child.lb": '''
            def init(module):
                module.name = "module:child"

            def prepare(module, options):
                return True

            def build(env):
                env.copy("file.txt", "child/file.txt")
            ''', "file.txt": "", "repo.lb": REPO_SINGLE.format('module.lb", "child.lb'),
                      "other/repo.lb": '''
            def init(repo):
                repo.name = "other"

            def prepare(repo, options):
                repo.add_modules_recursive(".")
            ''', "other/module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                env.copy("data.bin", "other/data.bin")
            ''', "other/data.bin": b"\x00\xff"})
        self.load(repositories=["repo.lb", "other/repo.lb"]).build(modules=["repo:**", "other:**"])
        observed = self.observed()

        self.assertFalse(observed["build"])
        self.assertEqual(["other", "repo"], observed["repositories"])
        self.assertEqual(["other:module", "repo:module", "repo:module:child"], observed["modules"])
        self.assertEqual([["other:module", "other", "other/data.bin", True],
                          ["repo:module", "repo", "repo/module/file.txt", True],
                          ["repo:module", "repo", "repo/module/template.txt", True],
                          ["repo:module:child", "repo", "child/file.txt", True]],
                         observed["operations"])
        self.assertEqual([op[2] for op in observed["operations"]], observed["iterated"])
        self.assertEqual({"repo:module": ["repo/module/file.txt", "repo/module/template.txt",
                                          "child/file.txt"],
                          "repo:module:child": ["child/file.txt"],
                          "repo": ["repo/module/file.txt", "repo/module/template.txt",
                                   "child/file.txt"],
                          "other": ["other/data.bin"], "missing": []}, observed["per_module"])
        self.assertEqual(["filename", "has_filename", "local_filename_out", "module",
                          "module_name", "repository"], observed["interface"])
        self.assertTrue(observed["late"])

    @unittest.expectedFailure
    def test_should_provide_output_path(self):
        # FIXME: accesses an attribute that does not exist
        observed = self.module(MODULE.format(name="module") + '''
def post_build(env):
    observe(outpath=env.buildlog.outpath)
''')
        self.assertEqual({"outpath": join(self.root, "out")}, observed)

    def test_should_support_metadata(self):
        self.project({"module.lb": '''
            def init(module):
                module.name = "module"

            def prepare(module, options):
                return True

            def build(env):
                env.add_metadata("key", "b", "a")
                env.append_metadata("key", "c")
                env.append_metadata_unique("key", "a")
                env.add_metadata("other", 1)
                env.copy("file.txt", metadata={"flags": ["-a", "-b"]})
                env.template("file.txt", "template.txt", metadata={"flags": "-c", "single": 1})
                env.extract("archive.zip", dest="extracted", metadata={"flags": ["-d"]})

            def post_build(env):
                log = env.buildlog
                observe(metadata=log.metadata, repo=log.repo_metadata, module=log.module_metadata,
                        operation=log.operation_metadata,
                        legacy=[[op.module_name, op.local_filename_out(), op.local_filename_out("sub")]
                                for op in log.get_operations_per_module("repo:module")
                                for op in [type(log.operations[0])(op)]][:1],
                        paths=[env.outpath("a", "b"), env.outpath("a", basepath="base"),
                               env.reloutpath("a/b", "a"), env.reloutpath("a"),
                               sorted(env.get_generated_local_files(lambda path: "t" in path)),
                               env.get_option("missing", 5), env.get_option(":module:missing")],
                        ignore=sorted(env.ignore_patterns("*.txt")("", ["a.txt", "b.c"])))
            ''', "file.txt": "", "archive.zip": self.archive()})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.build()
        observed = self.observed()

        self.assertEqual({"key": ["a", "b", "c"], "other": [1]}, observed["metadata"])
        self.assertEqual({"key": {"repo": ["a", "b", "c"]}, "other": {"repo": [1]}},
                         observed["repo"])
        self.assertEqual({"key": {"repo:module": ["a", "b", "c"]}, "other": {"repo:module": [1]}},
                         observed["module"])
        self.assertEqual({"flags": {"file.txt": ["-a", "-b"], "template.txt": ["-c"],
                                    "extracted/file.txt": ["-d"]},
                          "single": {"template.txt": [1]}}, observed["operation"])
        self.assertEqual([["repo:module", "extracted/file.txt", "../extracted/file.txt"]],
                         observed["legacy"])
        out = join(self.root, "out")
        self.assertEqual([join(out, "a/b"), join(out, "base/a"), "b", "a",
                          ["extracted/file.txt", "file.txt", "template.txt"], 5, None],
                         observed["paths"])
        self.assertEqual(["a.txt"], observed["ignore"])

        deprecated = [str(w.message) for w in caught if w.category is DeprecationWarning]
        for name in ("add_metadata", "append_metadata", "append_metadata_unique",
                     "copy(..., metadata=metadata)", "template(..., metadata=metadata)",
                     "extract(..., metadata=metadata)", "BuildLog.metadata",
                     "BuildLog.repo_metadata", "BuildLog.module_metadata",
                     "BuildLog.operation_metadata", "get_operations_per_module",
                     "BuildLogOperation.module_name", "local_filename_out", ".outpath(",
                     ".reloutpath(", "get_generated_local_files", "get_option",
                     "ignore_patterns"):
            self.assertTrue([message for message in deprecated if name in message], name)
        for message in deprecated:
            self.assertRegex(message, r"is deprecated since v1\.8\.0")

    def test_should_locate_deprecated_call_when_verbose(self):
        self.addCleanup(setattr, lbuild.facade, "VERBOSE_DEPRECATION", lbuild.facade.VERBOSE_DEPRECATION)
        lbuild.facade.VERBOSE_DEPRECATION = 1
        self.project({"module.lb": MODULE.format(name="module").replace(
            "pass", 'env.get_option("missing")')})

        with self.assertLogs("lbuild.facade", logging.WARNING) as logs, \
             self.assertWarns(DeprecationWarning):
            self.build()
        self.assertIn("module.lb", logs.output[0])
        self.assertIn("'EnvironmentBuild.get_option(key, default=None)' is deprecated since v1.8.0, "
                      "use 'EnvironmentBuild.get(key, default=None)' instead!", logs.output[0])


if __name__ == '__main__':
    unittest.main()
