
test:
	@python3 -m unittest discover -p *test.py

test-discover:
	python3 scripts/lbuild-discover -r test/resources/repo1.lb -r test/resources/repo2/repo2.lb --discover="repository:options"
	python3 scripts/lbuild-discover -r test/resources/repo1.lb -r test/resources/repo2/repo2.lb --discover="modules"
	python3 scripts/lbuild-discover -r test/resources/repo1.lb -r test/resources/repo2/repo2.lb --discover="module:options" -D":target=hosted" -c test/resources/test1.lb

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
	sudo -H pip3 install testfixtures coverage

# TODO: Also remove folder
uninstall:
	@cat uninstall.txt | xargs rm -rf
#rm -rf installed_files.txt

.PHONY : test dist install uninstall
