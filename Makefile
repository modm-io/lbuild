
test:
	@python3 -m unittest discover -p *test.py

dist:
	@python3 setup.py sdist --formats=zip

install:
	@python3 setup.py install --record uninstall.txt

install-user:
	@python3 setup.py install --user

# TODO: Also remove folder
uninstall:
	@cat uninstall.txt | xargs rm -rf
#rm -rf installed_files.txt

.PHONY : test dist install uninstall
