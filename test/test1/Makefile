
ROOTPATH = ../..

all:
	python3 $(ROOTPATH)/lbuild.py \
		-r $(ROOTPATH)/example/repo1 \
		-r $(ROOTPATH)/example/repo2 \
		-p test1.lb -vvv

clean:
	$(RM) -r src/
	$(RM) -r test/

.PHONY: all clean

