#!/bin/bash

set -e

version=72926603c44b331fc6eb417d1bd68816b6cee22d
date=2023-05-19

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

