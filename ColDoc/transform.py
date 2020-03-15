#!/usr/bin/env python3

""" the processor
 transforms LaTeX according to rules and tasks

"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil, re, json, pathlib
import os.path
from os.path import join as osjoin


if __name__ == '__main__':
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    COLDOC_SRC_ROOT=a
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)


############## ColDoc stuff

from ColDoc.config import *

from ColDoc.utils import *

from ColDoc.classes import MetadataBase



#########################################################################
from ColDoc import TokenizerPassThru

import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base

from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Packages import amsthm , graphicx

##############

def squash_uuid(inp, out, blobs_dir):
    " transforms all uuid"
    if not os.path.isabs(inp): inp = osjoin(blobs_dir, inp)
    thetex = TeX()
    thetex.input(open(inp), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    if isinstance(out,str):
        if not os.path.isabs(out): out = osjoin(blobs_dir, out)
        out = open(out,'w')
    itertokens = thetex.itertokens()
    forw_map = {}
    back_map = {}
    for tok in itertokens:
        if isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
            macroname = str(tok.macroName)
            # TODO do not alter preamble in main_file
            if macroname in ('input','include','input_preamble','include_preamble'):
                inputfile = thetex.readArgument(type=str)
                uuid, blob = file_to_uuid(inputfile, blobs_dir)
                if inputfile[:5] == 'UUID/':
                    text = uuid
                elif inputfile[:4] == 'SEC/':
                    text = os.path.dirname(inputfile)[4:].replace('_','\_')
                else:
                    logger.error('unsupported inputfile %r', inputfile)
                    text = uuid
                out.write(r'\uuidplaceholder{' + uuid + '}{' + text + '}')
                back_map[uuid] = macroname, inputfile
                forw_map[inputfile] = macroname, uuid
            else:
                out.write(tok.source)
        else:
            out.write(tok.source)
    return forw_map, back_map
