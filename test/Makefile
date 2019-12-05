latex_test:
	test -d tmp || mkdir tmp
	test -d tmp/lt || mkdir tmp/lt
	./latex_test.sh --SP --SI --CG
	./latex_test.sh --SP --SAT --SS --ZS --AU=no
	./latex_test.sh  --SAT  --ZS  --AU=no
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

