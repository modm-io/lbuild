
test:
	@python3 -W ignore::DeprecationWarning -m unittest discover -p *test.py

coverage:
	@coverage run --branch --source=lbuild -m unittest discover -p *test.py
	@coverage report
	@coverage html -d build/coverage

coverage-view:
	@xdg-open build/coverage/index.html&

pylint:
	@pylint lbuild

dist:
	@rm -rf dist
	@python3 -m build

install:
	@pip3 install .

install-user:
	@pip3 install --user .

install-prerequisites:
	pip3 install -e .[test]

upload: dist
	@twine upload --skip-existing dist/*

uninstall:
	@pip3 uninstall -y lbuild

docs:
	@cd docs && mkdocs build --strict

docs-serve:
	@cd docs && mkdocs serve

.PHONY : test dist install uninstall upload docs docs-serve
