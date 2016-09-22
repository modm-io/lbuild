
LBUILD=../../scripts/lbuild
REPOS=-r"../repo1/repo.lb" -r"../repo2/repo.lb"

all: project1 project2

project1:
	$(LBUILD) $(REPOS) -c project1.xml -o project1

project2:
	$(LBUILD) $(REPOS) -c project2.xml -o project2

discover:
	$(LBUILD)-discover $(REPOS) --discover=repository:options
	$(LBUILD)-discover $(REPOS) --discover=repository:options -D":target=hosted"
	$(LBUILD)-discover $(REPOS) --discover=modules -D":target=hosted"
	$(LBUILD)-discover $(REPOS) --discover=module:options -D":target=hosted" -m":module3"

clean:
	$(RM) -r project1
	$(RM) -r project2

.PHONY : project1 project2 clean
