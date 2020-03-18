#!/bin/sh
set -e
file="$1"
shift
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
echo python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b ${@} "$file"
python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b ${@} "$file"
echo ======= we need to copy graphic files, in case --CG was not passed
cp -a latex/F tmp/lt/b/F
echo ========= check that it compiles
cd tmp/lt/b
if ! ${LATEX} main.tex ; then
    echo FAILED, look in  tmp/lt/b/main.log
    exit 1
fi
cd "$c"
echo ========= deblob
python3 ../ColDoc/deblob_inator.py --blobs-dir=tmp/lt/b --latex-dir=tmp/lt/c
echo ========= diff
diff -urwbB "$file" tmp/lt/c
diff -ur "$file" tmp/lt/c || true
echo ========= check that it compiles
cp -a latex/F tmp/lt/c/F
cd tmp/lt/c
if ! ${LATEX} latex_test.tex ; then
    echo FAILED, look in  tmp/lt/c/main.log
    exit 1
fi
cd "$c"
echo ======================= SUCCESS
rm -rf tmp/lt/b tmp/lt/c

