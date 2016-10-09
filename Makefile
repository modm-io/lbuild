
test:
	@python3 -m unittest discover -p *test.py

test-discover:
	python3 scripts/lbuild -c test/resources/test1.lb discover-repository
	python3 scripts/lbuild -c test/resources/test1.lb discover-modules
	python3 scripts/lbuild -c test/resources/test1.lb discover-module-options
	python3 scripts/lbuild -c test/resources/test1.lb discover-module-options --module="repo1:other"
	python3 scripts/lbuild -c test/resources/test1.lb discover-option --option-name="repo1:target"
	python3 scripts/lbuild -c test/resources/test1.lb discover-option --option-name=":other:foo"

coverage:
	@coverage run --source=lbuild -m unittest discover -p *test.py
	@coverage report
	@coverage html -d build/coverage

pylint-gui:
	@cd lbuild; pylint-gui

dist:
	@python3 setup.py sdist --formats=zip

install:
	@python3 setup.py install --record uninstall.txt

install-user:
	@python3 setup.py install --user

install-prerequisites:
	# Required for the tests
	sudo -H pip3 install testfixtures coverage svn gitpython

# TODO: Also remove folder
uninstall:
	@cat uninstall.txt | xargs rm -rf
#rm -rf installed_files.txt

.PHONY : test dist install uninstall
