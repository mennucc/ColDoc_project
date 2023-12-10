#!/bin/bash

set -e

version=298a55b651d323283d08be75b4e32904afe30ca0
date=2023-09-23

b="$(dirname $( realpath $0 ))"
cd "$b"

if test -d plastex ; then
    cd plastex
    git checkout master
    git pull
else
    git clone https://github.com/plastex/plastex.git
    cd plastex
fi



if git branch | grep -q  master-$date ; then
    echo branch  master-$date exists
else
    git branch master-$date $version
fi

if git branch | grep -q patched-$date ; then
    echo branch  patched-$date exists
    git checkout patched-$date
else
    git branch patched-$date $version
    git checkout patched-$date
    git am  ../patches/*patch
fi

echo
echo
echo Now you may issue the command:
echo "cd $b/plastex ; pip3 install ."

