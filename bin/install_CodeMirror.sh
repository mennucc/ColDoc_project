#!/bin/bash

set -exv

cd $( dirname $( realpath $0) )
cd ..

if ! test -d node_modules ; then mkdir node_modules  ; fi



if which npmz ; then
    npm install codemirror
else
    cd node_modules 
    if ! test -f codemirror.zip ; then
	wget https://codemirror.net/codemirror.zip
    fi
    unzip codemirror.zip
    for D in codemirror-*; do
     if ! test -d codemirror ; then	
 	ln -s  $D codemirror 
     fi
    done
fi
