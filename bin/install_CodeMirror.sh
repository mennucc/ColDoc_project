#!/bin/bash

set -e

cd $( dirname $( realpath $0) )
cd ..

if ! test -d ColDocDjango/UUID ; then
    echo RUNTIME ERROR
    exit 1
fi

if ! test -d node_modules ; then mkdir node_modules  ; fi



if which npm ; then
    echo Install CodeMirror using npm
    npm install codemirror@5
else
    cd node_modules
    if ! test -f codemirror.zip ; then
	echo Download CodeMirror
	wget --quiet https://codemirror.net/codemirror.zip
    fi
    echo Unzip CodeMirror
    unzip -o -q  codemirror.zip
    for D in codemirror-*; do
     if ! test -d codemirror ; then	
 	ln -s  $D codemirror 
     fi
    done
fi


if ! test -L ColDocDjango/UUID/static/UUID/cm ; then
    ln -v -s -T  ../../../../node_modules/codemirror ColDocDjango/UUID/static/UUID/cm
fi
