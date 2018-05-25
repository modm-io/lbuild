
test:
	@python3 -W ignore::DeprecationWarning -m unittest discover -p *test.py

coverage:
	@coverage run --branch --source=lbuild -m unittest discover -p *test.py
	@coverage report
	@coverage html -d build/coverage

coverage-view:
	@xdg-open build/coverage/index.html&

pylint-gui:
	@cd lbuild; pylint-gui3

dist:
	@rm -rf dist
	@python3 setup.py sdist bdist_wheel

install:
	@python3 setup.py install --record uninstall.txt

install-user:
	@python3 setup.py install --user

install-prerequisites:
	sudo -H pip3 install -r requirements.txt

upload: dist
	@twine upload --skip-existing dist/*

# TODO: Also remove folder
uninstall:
	@cat uninstall.txt | xargs rm -rf
#rm -rf installed_files.txt

.PHONY : test dist install uninstall upload
