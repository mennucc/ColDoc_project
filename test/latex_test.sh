#!/bin/sh
set -e
ENGINE=pdflatex
file="$1"
shift
if test "$file" = '--engine' ; then
    ENGINE="$1"
    shift
    file="$1"
    shift
fi
c=`pwd`
LATEX="$ENGINE  -interaction batchmode -file-line-error"
echo ========================== results when blobinator has options : ${@}
test -d tmp
test -d tmp/lt
test -f latex_test.sh
#####
rm -rf tmp/lt/b tmp/lt/c
mkdir tmp/lt/b tmp/lt/c
echo ========== blob it
echo '$' python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b ${@} "$file"
python3 ../ColDoc/blob_inator.py --blobs-dir=tmp/lt/b ${@} "$file"
echo ========= check that it compiles
cd tmp/lt/b
if ! ${LATEX} main_eng.tex ; then
    echo '$ cd tmp/lt/b ' ${LATEX} main_eng.tex
    echo FAILED, look in  tmp/lt/b/main_eng.log
    exit 1
fi
cd "$c"
echo ========= deblob
echo '$' python3 ../ColDoc/deblob_inator.py --blobs-dir=tmp/lt/b --latex-dir=tmp/lt/c
python3 ../ColDoc/deblob_inator.py --blobs-dir=tmp/lt/b --latex-dir=tmp/lt/c
echo ========= diff
diff -ur `dirname ${file}` tmp/lt/c || true
echo ========= check that it compiles
cd tmp/lt/c
ln -s ../../../../tex/ColDocUUID.sty 
if ! ${LATEX} `basename ${file}` ; then
    echo '$ cd tmp/lt/c ; ' ${LATEX}  `basename ${file}`
    echo FAILED, look for logs in tmp/lt/c/
    exit 1
fi
cd "$c"
echo ======================= SUCCESS
rm -rf tmp/lt/b tmp/lt/c

