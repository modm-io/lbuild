# Installation

*lbuild* requires Python 3.11 or newer and is available [on PyPi][pypi]:

```sh
pip install lbuild
```

To upgrade an existing installation:

```sh
pip install --upgrade lbuild
```

You can also install the latest development version directly from GitHub:

```sh
pip install git+https://github.com/modm-io/lbuild.git@develop
```

Check that it works:

```sh
lbuild --version
lbuild -h
```


## Development

To work on *lbuild* itself, clone the repository and install it in editable
mode with the test dependencies:

```sh
git clone https://github.com/modm-io/lbuild.git
cd lbuild
pip install -e ".[test]"
make test
```

See the [conventions](../conventions.md) for the code style.

The documentation is built with [MkDocs][mkdocs] and the
[Material theme][material]:

```sh
pip install mkdocs-material
make docs-serve
```


[pypi]: https://pypi.org/project/lbuild
[mkdocs]: https://www.mkdocs.org
[material]: https://squidfunk.github.io/mkdocs-material
