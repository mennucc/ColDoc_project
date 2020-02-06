
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
	test -d tmp/pt || mkdir tmp/pt
	test -d tmp/pt/1 && rm -r tmp/pt/1
	cp -a -T paper tmp/pt/1
	rm -r  tmp/pt/1/F
	cp -a -T latex/F tmp/pt/1/F
	#
	cd tmp/pt/1 && pdflatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && pdflatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && mv -T paper.aux paper_latex.aux
	cd tmp/pt/1 && mv -T paper.log paper_latex.log
	cd tmp/pt/1 && mv -T paper.pdf paper_latex.pdf
	#
	cd tmp/pt/1 && xelatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && xelatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && mv -T paper.aux paper_xetex.aux
	cd tmp/pt/1 && mv -T paper.log paper_xetex.log
	cd tmp/pt/1 && mv -T paper.pdf paper_xetex.pdf
	#
	cd tmp/pt/1 && lualatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && lualatex -interaction batchmode -file-line-error paper.tex
	cd tmp/pt/1 && mv -T paper.aux paper_lualatex.aux
	cd tmp/pt/1 && mv -T paper.log paper_lualatex.log
	cd tmp/pt/1 && mv -T paper.pdf paper_lualatex.pdf
	#
	cd tmp/pt/1 && plastex --dir=xhtml --log  paper.tex && test -f xhtml/index.html
	cd tmp/pt/1 && plastex --dir=html5 --renderer=HTML5 --log  paper.tex && test -f html5/index.html


clean:
	test -d tmp/pt/1 && rm -r tmp/pt/1
