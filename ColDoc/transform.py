#!/usr/bin/env python3

""" the processor
 transforms LaTeX according to rules and tasks

"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil, re, json, pathlib, pickle
import os.path
from os.path import join as osjoin


# note that from python 3.6 on, `dict` preserves order
from collections import OrderedDict

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

class squash_helper_base(object):
    "base class, does nothing"
    def process_macro(self, macroname, thetex):
        return None
    def process_begin(self, begin, thetex):
        return None
    def process_end(self, end, thetex):
        return None
    def process_comment(self, comment, thetex):
        return None

class squash_helper_stack(squash_helper_base):
    "manages the stack"
    def __init__(self):
        self.stack = []
    #
    def process_begin(self, begin, thetex):
        self.stack.append('E_'+begin)
    #
    def process_end(self, end, thetex):
        end = 'E_' + end
        if not self.stack or end != self.stack.pop():
            logger.warning('disaligned stack')

class squash_input_uuid(squash_helper_stack):
    " replaces \\input and similar with placeholders; delete comments"
    def __init__(self, blobs_dir, blob, options):
        self.forw_map = OrderedDict()
        self.back_map = OrderedDict()
        self.blobs_dir =  blobs_dir
        self.blob = blob
        self.options = options
        self.input_macros = ['input','include','input_preamble','include_preamble','bibliography']
        self.input_macros_with_parameters = ['usepackage',]
        # macros where there may be multiple input files, separated by comma
        self.input_macros_comma_separated = ['usepackage','bibliography']
        # it is up to the caller to add other macros such as 'includegraphics'
        super().__init__()
    #
    def process_macro(self, macroname, thetex):
        if macroname in (self.input_macros + self.input_macros_with_parameters):
            argSource = ''
            if macroname in self.input_macros_with_parameters:
                for spec in '*','[]',None:
                    _, s = thetex.readArgumentAndSource(spec=spec)
                    if spec is None:
                        inputfile = s[1:-1]
                    else:
                        argSource += s
            else:   
                inputfile = thetex.readArgument(type=str)
            if macroname in self.input_macros_comma_separated:
                inputfiles = inputfile.split(',')
            else:
                inputfiles = [inputfile]
            placeholder = ''
            for inputfile in inputfiles:
                inputfile = inputfile.strip()
                if  macroname == 'usepackage' and inputfile[:5] != 'UUID/':
                    placeholder += '\\' + macroname + argSource + '{' + inputfile + '}'
                    continue
                try:
                    uuid, blob = file_to_uuid(inputfile, self.blobs_dir)
                except Exception as e:
                    logger.error('Macro %r %r { %r } could not be parsed: %r', macroname, argSource, inputfile, e)
                    placeholder += '\\' + macroname + argSource + '{' + inputfile + '}'
                    continue
                if inputfile[:5] == 'UUID/':
                    text = uuid
                elif inputfile[:4] == 'SEC/':
                    text = os.path.dirname(inputfile)[4:].replace('_','\_')
                else:
                    logger.debug('while squashing, no good text substitution for inputfile %r uuid %r blob %r', inputfile, uuid, blob)
                    text = uuid
                context = self.stack[-1]  if self.stack else None
                self.back_map[uuid] = macroname, inputfile, context
                self.forw_map[inputfile] = macroname, uuid
                placeholder += (r'\uuidplaceholder{' + uuid + '}{' + text + '}')
            return placeholder
        else:
            return None
    #
    def process_comment(self, comment, thetex):
        "deletes comments"
        return '%\n'

class squash_helper_reparse_metadata(squash_input_uuid):
    "reparse metadata"
    def __init__(self, blobs_dir, metadata, options, *v, **k):
        self.metadata_command = options['metadata_command']
        self.metadata = []
        super().__init__(blobs_dir, metadata, options, *v, **k)
    #
    def process_macro(self, macroname, thetex, environ=None):
        r = super().process_macro(macroname, thetex)
        if r is not None:
            return r
        if macroname not in self.metadata_command:
            return None
        # keep this in sync with ColDoc.blob_inator, around line 1060
        obj = thetex.ownerDocument.createElement(macroname)
        thetex.currentInput[0].pass_comments = False
        ## FIXME why is this attribute not there...
        if hasattr(obj,'nargs'):
            N=obj.nargs
        else:
            logger.debug('nargs wrong for '+repr(obj))
            N = 1
        args = [ thetex.readArgumentAndSource(type=str)[1] for j in range(N)]
        #obj.parse(thetex)
        thetex.currentInput[0].pass_comments = True
        logger.info('metadata %r  %r' % (macroname,args))
        #
        a = '' if not self.stack else ('S_'+self.stack[-1]+'_')
        for j in args:
            j =  j.translate({10:32})
            self.metadata.append((a+'M_'+macroname,j))

def squash_latex(inp, out, blobs_dir, options, helper=None):
    " transforms LaTeX file"
    if helper is None:
        helper = squash_helper_base()
    if not os.path.isabs(inp): inp = osjoin(blobs_dir, inp)
    thetex = TeX()
    thetex.input(open(inp), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    if isinstance(out,str):
        if not os.path.isabs(out): out = osjoin(blobs_dir, out)
        out = open(out,'w')
    itertokens = thetex.itertokens()
    squash_recurse(out, thetex, itertokens, options, helper)
    return helper

def squash_recurse(out, thetex, itertokens, options, helper, beginenvironment=None):
    for tok in itertokens:
        if isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
            macroname = str(tok.macroName)
            if macroname == 'begin':
                begin = thetex.readArgument(type=str)
                if begin in options["verbatim_environment"]:
                    out.write('\\begin{%s}' % begin)
                    class MyVerbatim(Base.verbatim):
                            macroName = begin
                    obj = MyVerbatim()
                    obj.ownerDocument = thetex.ownerDocument
                    t = obj.invoke(thetex)
                    for j in t[1:]:
                        out.write(j)
                    out.write('\\end{%s}' % begin)
                    # the above pushes the \end{verbatim} back on stack: discard it
                    try:
                        next(itertokens)
                    except:
                        logger.warning('premature end of \\begin{%s}',begin)
                else:
                    r = helper.process_begin(begin, thetex)
                    out.write(r if r is not None else ('\\begin{'+begin+'}'))
                    squash_recurse(out, thetex, itertokens, options, helper, begin)
            elif macroname == 'end':
                end = thetex.readArgument(type=str)
                r = helper.process_end(end,thetex)
                out.write(r if r is not None else ('\\end{'+end+'}'))
                if end != beginenvironment:
                    logger.warning(" begin %r ended by end%r ",beginenvironment,end)
                return
            elif macroname == 'verb':
                obj = Base.verb()
                obj.ownerDocument = thetex.ownerDocument
                t = obj.invoke(thetex)
                out.write('\\verb')
                for j in t[1:]:
                    out.write(j)
                del obj,j,t
            else:
                r = helper.process_macro(macroname,thetex)
                out.write(r if r is not None else tok.source)
                # TODO do not alter preamble in main_file
        elif isinstance(tok, TokenizerPassThru.Comment):
            r = helper.process_comment(str(tok.source),thetex)
            out.write(r if r is not None else tok.source)
        else:
            out.write(tok.source)



#############################

import io

def reparse_metadata(inp, metadata, blobs_dir, options):
    " reparse metadata of LaTeX file"
    #
    from .transform import squash_helper_reparse_metadata
    helper = squash_helper_reparse_metadata(blobs_dir, metadata, options)
    from ColDoc.latex import environments_we_wont_latex
    if metadata.environ not in environments_we_wont_latex:
        helper.input_macros_with_parameters += options['split_graphic']
    #
    if not os.path.isabs(inp): inp = osjoin(blobs_dir, inp)
    thetex = TeX()
    mydocument = thetex.ownerDocument
    mycontext = mydocument.context
    #
    # give it some context
    mycontext.loadPackage(thetex, 'article.cls', {})
    #if args.split_sections:
    #    mycontext.newcommand('section',1,r'\section{#1}')
    #    mycontext.newcommand('subsection',1,r'\subsection{#1}')
    for name in options['metadata_command'] :
        d =  '\\' + name + '{#1}'
        #mycontext.newcommand(name, n, d)
        n = 1
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':n, 'opt':None, 'definition':d})
        assert newclass.nargs == n
        mycontext.addGlobal(name, newclass)
    #
    thetex.input(open(inp), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    out = io.StringIO()
    itertokens = thetex.itertokens()
    squash_recurse(out, thetex, itertokens, options, helper)
    #
    a = osjoin(os.path.dirname(inp),'.back_map.pickle')
    pickle.dump(helper.back_map,open(a,'wb'),)
    #
    return helper.back_map, helper.metadata


