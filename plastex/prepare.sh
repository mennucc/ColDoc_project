#!/bin/bash

set -e

version=a882a62b81e6ae7b8c9454ae2b222ef5c2c14bb1
date=2023-07-03

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

