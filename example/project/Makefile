
LBUILD=../../scripts/lbuild

all: project1 project2

project1:
	$(LBUILD) -r ../repo1/repo.lb -r ../repo2/repo.lb -o project1 -c project1.xml

project2:
	$(LBUILD) -r ../repo1/repo.lb -r ../repo2/repo.lb -o project2 -c project2.xml

clean:
	$(RM) -r project1
	$(RM) -r project2

.PHONY : project1 project2 clean
