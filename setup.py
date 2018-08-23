#!/usr/bin/env python3
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

from setuptools import setup, find_packages

setup(
    name = "modm-lbuild",
    version = "0.3.5",
    entry_points={
        'console_scripts': [
            'lbuild = lbuild.main:main',
        ],
    },

    packages = find_packages(exclude=["test"]),

    include_package_data = True,

	# Make sure all files are unzipped during installation
	#zip_safe = False,

    install_requires = ['lxml', 'jinja2', 'gitpython'],

    extras_require = {
        "test": ['testfixtures', 'coverage'],
    },

    # Metadata
    author = "Fabian Greif",
    author_email = "fabian.greif@rwth-aachen.de",
    description = "Library builder to create a compilable library from " \
    			  "a set of template files for different target environments",
    license = "BSD",
    keywords = "library builder generator",
    url = "https://github.com/modm-io/library-builder",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Embedded Systems",
    ],
)
