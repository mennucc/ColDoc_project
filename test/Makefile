
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
	./latex_test.sh latex/latex_test.tex --SAT  --ZS  --AU=no --split-paragraph 120 --SL=itemize
	./latex_test.sh latex/latex_test.tex --SAT  --ZS  --split-paragraph 120 --SL=itemize
	./latex_test.sh latex/latex_test.tex --SP --SI
	./latex_test.sh latex/latex_test.tex --SP --SAT --SS --ZS --AU=no
	./latex_test.sh latex/latex_test.tex --SAT  --ZS  --AU=no
	#
	@echo ==========================  all cmds
	rm -rf tmp/lt/b   tmp/lt/c
	mkdir tmp/lt/b  tmp/lt/c
	@echo ========== blobify it
	python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b --SP --SL=itemize --SAT --SI  --EDB latex/latex_test.tex
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
	cp -a -t  tmp/pt  paper/*.sty
	cd tmp/pt ; ln -sf ../../../tex/*sty .
	cp -a -T latex/F tmp/pt/F
	cp -a -T paper/subdir tmp/pt/subdir
	#
	sed -i~~~ 's/%\\usepackage{coldoc_ifs}/\\usepackage{coldoc_ifs}/' tmp/pt/paper.tex
	#
	cd tmp/pt && pdflatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt && bibtex paper
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


django_help:
	@echo "Use 'make target' with target being:"
	@echo " django_deploy : to create a test portal in $(COLDOC_SITE_ROOT) "
	@echo " django_paper  : to add paper/paper.tex to that portal"
	@echo " django_book   : to add book/book.tex to that portal"
	@echo " django_latextest : to add latex/latex_test.tex to that portal (a stress test)"
	@echo " django_run    : to run a local server to test django portal "
	@echo " django_tasks  : to run the server for background tasks"
	@echo " django_clean  : to clean everything "

########## deploy a ColDoc portal
$(COLDOC_SITE_ROOT)/.__deployed_timestamp:
	test -d tmp || mkdir tmp
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT)  deploy
	#### tweak config.ini
	# change to DEBUG mode, and store dedup files inside the static tree, so they will be available in DEBUG mode
	sed -i~~ 's!debug.*!debug = True!;s!dedup_root.*!dedup_root = %(site_root)s/static_local/dedup!;s!dedup_url.*!dedup_url = /static/dedup!' $(COLDOC_SITE_ROOT)/config.ini
	mkdir $(COLDOC_SITE_ROOT)/static_local/dedup
	# enable whitenoise
	sed -i~~~ 's/whitenoise.*False/whitenoise = True/' $(COLDOC_SITE_ROOT)/config.ini
	# enable wallet if properly symlinked
	if test -f ../ColDocDjango/wallet/admin.py ; then 	sed -i~~~ 's/wallet.*False/wallet = True/' $(COLDOC_SITE_ROOT)/config.ini ; fi
	####
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  makemigrations
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  migrate
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT)  set_site
	# this is not really used since `manage.py runserver` ignores the static_root directory
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  collectstatic
	## this seems useless
	#	cd $(COLDOC_SITE_ROOT)/static_local &&  cp -a ../static_root/* . && ln -s ../static_root/CDdedup .
	../ColDocDjango/helper.py  --coldoc-site-root $(COLDOC_SITE_ROOT)  create_fake_users
	touch $(COLDOC_SITE_ROOT)/.__deployed_timestamp


django_deploy: $(COLDOC_SITE_ROOT)/.__deployed_timestamp

# load a paper in the ColDoc portal
django_paper: $(COLDOC_SITE_ROOT)/.__deployed_timestamp
	test  -f $(COLDOC_SITE_ROOT)/config.ini
	if  ./django_tester.py --coldoc-nick=paper isthere ; then  ./django_tester.py --coldoc-nick=paper delete ; fi
	if test -d $(COLDOC_SITE_ROOT)/coldocs/paper/blobs ; then  rm -rf  $(COLDOC_SITE_ROOT)/coldocs/paper ; fi
	../ColDocDjango/blob_inator.py --lang eng --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=paper  --ZS --SP --SE=figure --SL=description  --editor=ed_itor --author=jsmith --private-environment=privateremark  --private-environment=buyablecontent --SAT   paper/paper.tex
	./django_tester.py --coldoc-nick=paper isthere
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper --parent-uuid 007  --user jsmith --p_lang eng --c_lang eng --environ E_description add_blob
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper --parent-uuid 007  --user jsmith --p_lang eng --c_lang eng --environ E_privateremark add_blob
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper --parent-uuid 007  --user jsmith --p_lang eng --c_lang zxx --environ graphic_file add_blob
	../ColDocDjango/latex.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=paper --url-UUID="http://localhost:8000/UUID/paper/" all
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper --lang eng  reparse_all
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper check_tree
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick paper list_authors

# load a multi-lingual paper in the ColDoc portal
django_multlang: $(COLDOC_SITE_ROOT)/.__deployed_timestamp
	test  -f $(COLDOC_SITE_ROOT)/config.ini
	if  ./django_tester.py --coldoc-nick=multlang isthere ; then  ./django_tester.py  --coldoc-nick=multlang delete ; fi
	if test -d $(COLDOC_SITE_ROOT)/coldocs/multlang/blobs ; then  rm -rf  $(COLDOC_SITE_ROOT)/coldocs/multlang ; fi
	../ColDocDjango/blob_inator.py --lang mul,eng,ita --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=multlang  --ZS --SP --SE=figure --SL=description  --editor=ed_itor --author=jsmith --private-environment=privateremark  --private-environment=buyablecontent --latex-engine xelatex --SAT   multlang/paper.tex
	./django_tester.py --coldoc-nick=multlang isthere
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang --parent-uuid 007  --user jsmith --p_lang mul --c_lang mul --environ E_description add_blob
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang --parent-uuid 007  --user jsmith --p_lang mul --c_lang mul --environ E_privateremark add_blob
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang --parent-uuid 007  --user jsmith --p_lang mul --c_lang zxx --environ graphic_file add_blob
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang gen_lang
	../ColDocDjango/latex.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=multlang --url-UUID="http://localhost:8000/UUID/multlang/" all
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang --lang mul  reparse_all
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang check_tree
	../ColDocDjango/helper.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick multlang list_authors


# load a book in the ColDoc portal
django_book: $(COLDOC_SITE_ROOT)/.__deployed_timestamp
	test  -f $(COLDOC_SITE_ROOT)/config.ini
	if  ./django_tester.py --coldoc-nick=book isthere ; then  ./django_tester.py --coldoc-nick=book delete ; fi
	if test -d $(COLDOC_SITE_ROOT)/coldocs/book/blobs ; then  rm -rf  $(COLDOC_SITE_ROOT)/coldocs/book ; fi
	../ColDocDjango/blob_inator.py  --lang eng  --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=book  --ZS --SP --SE=figure --SL=description  --editor=ed_itor --author=jdoe --private-environment=privateremark  --private-environment=buyablecontent --SAT   book/book.tex
	./django_tester.py --coldoc-nick=book  isthere
	../ColDocDjango/latex.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=book --url-UUID="http://localhost:8000/UUID/book/" all


# load a latex test in the ColDoc portal
django_latextest: $(COLDOC_SITE_ROOT)/.__deployed_timestamp
	test  -f $(COLDOC_SITE_ROOT)/config.ini
	if  ./django_tester.py --coldoc-nick=latextest isthere ; then  ./django_tester.py --coldoc-nick=latextest delete ; fi
	if test -d $(COLDOC_SITE_ROOT)/coldocs/latextest/blobs ; then  rm -rf  $(COLDOC_SITE_ROOT)/coldocs/latextest ; fi
	../ColDocDjango/blob_inator.py  --lang eng  --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=latextest  --ZS --SP --SE=figure --SL=itemize --author=jsmith --SAT   latex/latex_test.tex
	./django_tester.py --coldoc-nick=latextest isthere
	../ColDocDjango/latex.py --coldoc-site-root $(COLDOC_SITE_ROOT) --coldoc-nick=latextest --url-UUID="http://localhost:8000/UUID/latextest/" all


django_run:
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  runserver

django_tasks:
	../ColDocDjango/manage.py --coldoc-site-root $(COLDOC_SITE_ROOT)  process_tasks --dev -v 2


django_paper_clean:
	-./django_tester.py delete
	rm -rf  $(COLDOC_SITE_ROOT)/coldocs/paper

django_clean: django_paper_clean
	if test -d $(COLDOC_SITE_ROOT)/var -a -f $(COLDOC_SITE_ROOT)/config.ini ; then trash-put -v $(COLDOC_SITE_ROOT) ; fi


############################

clean: django_clean
	rm -rf tmp/pt/1
