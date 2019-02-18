#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from setuptools import setup, find_packages
from lbuild.__init__ import __version__

with open("README.md") as f:
    long_description = f.read()

setup(
    name = "lbuild",
    version = __version__,
    python_requires=">=3.5.0",
    entry_points={
        "console_scripts": [
            "lbuild = lbuild.main:main",
        ],
    },

    packages = find_packages(exclude=["test"]),

    include_package_data = True,

	# Make sure all files are unzipped during installation
	#zip_safe = False,

    install_requires = ["lxml",
                        "jinja2",
                        "gitpython>=2.1.11",
                        "anytree>=2.4.3",
                        "colorful==0.4.4"],

    extras_require = {
        "test": ["testfixtures", "coverage"],
    },

    # Metadata
    author = "Fabian Greif, Niklas Hauser",
    author_email = "fabian.greif@rwth-aachen.de, niklas@salkinium.com",
    description = "Generic, modular code generator using the Jinja2 template engine.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license = "BSD",
    keywords = "library builder generator",
    url = "https://github.com/modm-io/lbuild",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Topic :: Software Development",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Embedded Systems",
    ],
)
