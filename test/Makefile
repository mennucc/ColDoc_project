
help:
	@echo "This Makefile contains many tests. Use 'make target' with target being:"
	@echo " latex_test  : to test blob_inator.py and deblob_inator.py  on latex/latex_test.tex"
	@echo " paper_test  : to test compilation of paper/paper.tex with many engines, and plasTeX"
	@echo " django_help : to see the list of tests for the ColDoc portal "
	@echo " clean       : to clean "

########## this tests blob_inator and deblob_inator repeatdly

latex_test:
	test -d tmp || mkdir tmp
	test -d tmp/lt || mkdir tmp/lt
	./latex_test.sh latex/latex_test.tex --SP --SI --CG
	./latex_test.sh latex/latex_test.tex --SP --SAT --SS --ZS --AU=no
	./latex_test.sh latex/latex_test.tex --SAT  --ZS  --AU=no
	#
	@echo ==========================  all cmds
	rm -rf tmp/lt/b   tmp/lt/c
	mkdir tmp/lt/b  tmp/lt/c
	@echo ========== blobify it
	python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b --SP --SL=itemize --SAT --SI --CG --EDB latex/latex_test.tex
	@echo ======== deblobify it
	python3 ../ColDoc/deblob_inator.py --blobs-dir=tmp/lt/b --latex-dir=tmp/lt/c --AUC
	@echo "======= diff (it will be different)"
	-diff -ur latex/latex_test.tex tmp/lt/c
	rm -rf tmp/lt/b   tmp/lt/c

########## this tests conditionals

paper_test:
	test -d tmp || mkdir tmp
	rm -fr tmp/pt
	test -d tmp/pt || mkdir tmp/pt
	cp -a -t  tmp/pt  paper/*.tex
	cd tmp/pt ; ln -s ../../../tex/*sty .
	cp -a -T latex/F tmp/pt/F
	#
	cd tmp/pt && pdflatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && pdflatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && mv -T paper.aux paper_latex.aux
	cd tmp/pt && mv -T paper.log paper_latex.log
	cd tmp/pt && mv -T paper.pdf paper_latex.pdf
	#
	cd tmp/pt && xelatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && xelatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && mv -T paper.aux paper_xetex.aux
	cd tmp/pt && mv -T paper.log paper_xetex.log
	cd tmp/pt && mv -T paper.pdf paper_xetex.pdf
	#
	cd tmp/pt && lualatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && lualatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && mv -T paper.aux paper_lualatex.aux
	cd tmp/pt && mv -T paper.log paper_lualatex.log
	cd tmp/pt && mv -T paper.pdf paper_lualatex.pdf
	#
	cd tmp/pt && plastex --dir=xhtml --log  paper.tex && test -f xhtml/index.html
	cd tmp/pt && plastex --dir=html5 --renderer=HTML5 --log  paper.tex && test -f html5/index.html


#############################


export COLDOC_SITE_ROOT=$(shell pwd)/tmp/test_site
COLDOC_URL="http://localhost:8000/UUID/paper/"

django_help:
	@echo "Use 'make target' with target being:"
	@echo " django_deploy : to create a test portal in $(COLDOC_SITE_ROOT) "
	@echo " django_paper  : to add paper/paper.tex to that portal"
	@echo " django_run    : to run a local server to test django portal "
	@echo " django_clean  : to clean everything "

########## deploy a ColDoc portal
$(COLDOC_SITE_ROOT)/.__deployed_timestamp:
	test -d tmp || mkdir tmp
	../ColDocDjango/admin.py  --coldoc-site-root $(COLDOC_SITE_ROOT)  deploy
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  makemigrations
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  migrate
	# this is not really used since `manage.py runserver` ignores the static_root directory
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  collectstatic
	cd $(COLDOC_SITE_ROOT)/static_local &&  cp -a ../static_root/* .
	sed -i~~ 's/debug.*False/debug = True/' $(COLDOC_SITE_ROOT)/config.ini
	../ColDocDjango/admin.py  --coldoc-site-root $(COLDOC_SITE_ROOT)  create_fake_users
	touch $(COLDOC_SITE_ROOT)/.__deployed_timestamp


django_deploy: $(COLDOC_SITE_ROOT)/.__deployed_timestamp

# load a paper in the ColDoc portal
django_paper: $(COLDOC_SITE_ROOT)/.__deployed_timestamp
	test  -f $(COLDOC_SITE_ROOT)/config.ini
	if  ./django_tester.py isthere ; then  ./django_tester.py delete ; fi
	if test -d $(COLDOC_SITE_ROOT)/coldocs/paper/blobs ; then  rm -r  $(COLDOC_SITE_ROOT)/coldocs/paper ; fi
	../ColDocDjango/blob_inator.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=paper  --ZS --SP --SE=document --SL=itemize --author=jsmith --private-environment=privateremark --SAT --CG  paper/paper.tex
	./django_tester.py isthere
	../ColDoc/latex.py --blobs-dir=$(COLDOC_SITE_ROOT)/coldocs/paper/blobs --url-UUID=$(COLDOC_URL) all
	../ColDoc/latex.py --blobs-dir=$(COLDOC_SITE_ROOT)/coldocs/paper/blobs --url-UUID=$(COLDOC_URL) main

django_run:
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  runserver

django_paper_clean:
	-./django_tester.py delete
	rm -rf  $(COLDOC_SITE_ROOT)/coldocs/paper

django_clean: django_paper_clean
	if test -d $(COLDOC_SITE_ROOT)/var -a -f $(COLDOC_SITE_ROOT)/config.ini ; then trash-put -v $(COLDOC_SITE_ROOT) ; fi


############################

clean: django_clean
	rm -rf tmp/pt/1
