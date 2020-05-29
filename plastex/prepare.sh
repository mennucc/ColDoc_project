#!/bin/bash

set -e

cd $( dirname $( realpath $0 ))

git clone https://github.com/plastex/plastex.git

cd plastex

git branch master-2020-05-20 7a855618a648c36

git branch patched-2020-05-20 7a855618a648c36

git checkout patched-2020-05-20

git am  ../patches/*


