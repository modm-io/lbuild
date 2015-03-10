
from setuptools import setup, find_packages

setup(
	name = "l.gen",	
	version = "0.1",
	packages = find_packages(exclude=["test"]),
	scripts = ['l.gen'],

	# Project uses reStructuredText, so ensure that the docutils get
	# installed or upgraded on the target machine
	install_requires = ['lxml'],
	
	# Metadata
	author = "Fabian Greif",
    author_email = "fabian.greif@rwth-aachen.de",
    description = "Library builder to create a compilable library from a set of template files for different target environments",
    license = "BSD",
    keywords = "library generator",
    url = "https://github.com/dergraaf/library-builder",
	classifiers = [
		"Development Status :: 2 - Pre-Alpha",
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

