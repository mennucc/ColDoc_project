#!/bin/bash

set -e

version=2cbc5858984756ea64069cf94866b140ba3a069f
date=2021-01-16

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
    git am  ../patches/*
fi

echo now you may issue the command:
echo "cd $b/plastex ; python3 setup.py install"

