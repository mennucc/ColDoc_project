#!/bin/sh
set -e
c=`pwd`
LATEX="pdflatex -interaction batchmode -file-line-error"
echo ========================== ${@}
test -d tmp
test -d tmp/lt
test -f latex_test.sh
#####
rm -rf tmp/lt/b tmp/lt/c
mkdir tmp/lt/b tmp/lt/c
echo ========== blob it
python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b ${@} latex/latex_test.tex
echo ======= we need to copy graphic files, in case --CG was not passed
cp -a latex/F tmp/lt/b/F
echo ========= check that it compiles
cd tmp/lt/b
${LATEX} main.tex
cd "$c"
echo ========= deblob
python3 ../ColDoc/deblob_inator.py --blobs-dir=tmp/lt/b --latex-dir=tmp/lt/c
echo ========= diff
diff -urwbB latex/latex_test.tex tmp/lt/c
diff -ur latex/latex_test.tex tmp/lt/c || true
echo ========= check that it compiles
cp -a latex/F tmp/lt/c/F
cd tmp/lt/c
${LATEX} latex_test.tex
cd "$c"
echo ======================= SUCCESS
rm -rf tmp/lt/b tmp/lt/c

