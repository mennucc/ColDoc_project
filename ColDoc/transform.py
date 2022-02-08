#!/usr/bin/env python3

""" the processor
 transforms LaTeX according to rules and tasks
 
 dedollarize [FILE]
    change $...$ to \(...\) and $$...$$ to \[...\]

"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil, re, json, pathlib, pickle, enum, tempfile
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

import ColDoc.utils
from ColDoc.classes import MetadataBase



#########################################################################
from ColDoc import TokenizerPassThru

import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base, plasTeX.Logging


from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Base.LaTeX import FontSelection, DimenCommand, StartSection

from plasTeX.Packages import amsthm , graphicx

##############

#opening and closing macros

macros_begin_end = {
    'bgroup':'egroup',
    'begingroup':'endgroup',
    '[':']',
    '(':')',
    # NO THIS IS A TOKEN '{':'}',
}


helper_help = """
helpers are used by the squash_recurse function

they have three methods, to process either a Macro, a Begin or an End

if they will not process it, they return None : 
this is useful when stacking helpers

if they process it, they return a new, processed, string 

or otherwise they return a tuple, that is a list of commands

"""

class helper_command(enum.Enum):
    WRITE = 1
    POPSTACK = 2
    NORECURSE = 3

class squash_helper_base(object):
    "base class, does nothing"
    input_filename = None
    #
    def process_macro(self, tok, thetex):
        return None
    def process_begin(self, begin, thetex):
        return None
    def process_end(self, end, thetex):
        return None
    def process_comment(self, comment, thetex):
        return None
    def process_token(self, tok, thetex, is_ending):
        return None

class squash_helper_stack(squash_helper_base):
    "manages the stack"
    def __init__(self):
        self.__stack = []
    #
    def process_begin(self, begin, thetex):
        self.stack_push('E_'+begin)
    #
    def process_end(self, end, thetex):
        end = 'E_' + end
        self.stack_pop(end)
    #
    @property
    def stack(self):
        return tuple(self.__stack)
    #
    def stack_push(self, begin):
        #print(self.input_filename, self.__stack,' + ',begin)
        self.__stack.append(begin)
    #
    def stack_pop_aggressive(self, end):
        #print(self.input_filename, self.__stack,' - ',end)
        if not self.__stack:
            logger.warning('file %r : disaligned stack, end of %r but stack is empty', self.input_filename, end)
            return False
        else:
            pop = self.__stack.pop()
            if pop != end:
                logger.warning('file %r : disaligned stack, popped %r instead of %r', self.input_filename, pop, end)
                return pop
            return True
    #
    def stack_pop(self, end):
        #print(self.input_filename, self.__stack,' ? ',end)
        if not self.__stack:
            logger.warning('file %r : disaligned stack, end of %r but stack is empty', self.input_filename, end)
            return False
        else:
            top = self.__stack[-1]
            if top == end:
                self.__stack.pop()
                logger.debug('file %r : top stack is %r , popped', self.input_filename, top)
                return False
            else:
                logger.warning('file %r : disaligned stack, top is %r instead of %r, not popping', self.input_filename, top, end)
                return top

class squash_modernize_dollars(squash_helper_stack):
    remap = {
        ('$',False) : '\(',
        ('$',True) : '\)',
        ('$$',False) : '\[',
        ('$$',True) : '\]',
    } 
    def process_token(self, tok, thetex, is_ending):
        if tok in ('$','$$'):
            k = tok, is_ending
            return self.remap[k]
        return tok


class squash_input_uuid(squash_helper_stack):
    " replaces \\input and similar with placeholders; delete comments"
    def __init__(self, blobs_dir, blob, options, load_uuid=None):
        self.forw_map = OrderedDict()
        self.back_map = OrderedDict()
        self.blobs_dir =  blobs_dir
        self.blob = blob
        self.options = options
        self.load_uuid = load_uuid
        self.input_macros = ['input','include','input_preamble','include_preamble','bibliography']
        self.input_macros_with_parameters = ['usepackage',]
        # macros where there may be multiple input files, separated by comma
        self.input_macros_comma_separated = ['usepackage','bibliography']
        # it is up to the caller to add other macros such as 'includegraphics'
        super().__init__()
    #
    def process_macro(self, tok, thetex):
        macroname = str(tok.macroName)
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
                    uuid, blob = ColDoc.utils.file_to_uuid(inputfile, self.blobs_dir)
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
                if ColDoc_add_env_when_squashing and self.load_uuid is not None:
                    try:
                        child = self.load_uuid(uuid)
                        if child.environ in ColDoc_environments_sectioning:
                            optarg = json.loads(child.optarg)
                            optarg[0] = '*'
                            placeholder +=  '\\' + child.environ + ''.join(optarg)
                    except:
                        logger.exception('While adding env %r with optarg %r of uuid %r', child.environ, child.optarg, uuid)
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
    def process_macro(self, tok, thetex, environ=None):
        macroname = str(tok.macroName)
        r = super().process_macro(tok, thetex)
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

class squash_helper_token2unicode(squash_helper_stack):
    " replaces \\input and similar with placeholders; delete comments"
    def __init__(self):
        self.counter = 0
        self.token_map = OrderedDict()
        self.unicode_map = OrderedDict()
        super().__init__()
    #
    __ranges = (
        (0x12000, 0x123FF), # cuneiform    U+12000 to U+123FF
        (0x10600, 0x1072F),        # Linear A Range: 10600–1077F but we stop at 10600–1072F
        ( 0x2C00,  0x2C5F), # Glagolitic Range: 2C00–2C5F
        (0x13000, 0x1342E), # Egyptian Hieroglyphs    Range: 13000–1342F  but the last one is undefined
        # Linear B Syllabary        Range: 10000–1007F     there are some holes
        #Cypriot   Unicode range    U+10800–U+1083F          there are some holes
        ( 0xE000,  0xF8FF), # first private area
        (0xF0000, 0xFFFFD),  # second private area
    )
    #
    def max_key(self):
        k = 0
        for s,e in self.__ranges:
            w = e-s
            k += w
        return k
    #
    def key2text(self, k):
        for s,e in self.__ranges:
            w = e-s
            if k < w:
                return chr(k + s)
            k -= w
        # Three private use areas are defined: one in the Basic Multilingual Plane (U+E000–U+F8FF),
        # and one each in, and nearly covering, planes 15 and 16 (U+F0000–U+FFFFD, U+100000–U+10FFFD)
        assert False, 'out of private area , see https://en.wikipedia.org/wiki/Private_Use_Areas'
        return None
    #
    def text2key(self, t):
        assert len(t) == 1
        t = ord(t)
        k = 0
        for s,e in self.__ranges:
            w = e-s
            if s <= t and t <=  e:
                return t + k - s
            k += w
        #
        raise ValueError('out of unicode key space:  %x' % (t,) )
    #
    def __remap(self, s):
        if s not in self.token_map:
            u = self.counter 
            self.token_map[s] = u
            self.unicode_map[u] = s
            self.counter += 1
        else:
            u = self.token_map[s]
        return self.key2text(u)
    #
    def __recurse(self, env_from, env_upto, thetex):
        basehelper = squash_helper_stack()
        basehelper.stack_push(env_from)
        basehelper.input_filename = 'SUB ' + str(self.input_filename)
        newout = io.StringIO()
        #print('recurse up to ',env_upto)
        squash_recurse(newout, thetex, self.itertokens, self.options, basehelper, env_upto)
        #print('recursed ended up to ',env_upto)
        s = newout.getvalue()
        #s = re.sub(" +", ' ',s)
        return s
    #
    def process_begin(self, begin, thetex):
        super().process_begin(begin, thetex)
        s = r'\begin{' + begin + '}'
        obj = thetex.ownerDocument.createElement(begin)
        if obj.mathMode:
            obj.parse(thetex)
            s += obj.argSource
            s += self.__recurse('E_'+begin, 'E_'+begin, thetex)
            super().process_end(begin, thetex)
            #print('parsing math',begin,'got',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
        return self.__remap(s)
    #
    def process_token(self, tok, thetex, is_ending):
        if tok in ('$','$$'):
            if is_ending:
                logger.warning(' problema 32kbgve9w8')
            s = tok +  self.__recurse(tok,tok, thetex)
            #print('tokenized dollars ',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
    #
    def process_end(self, end, thetex):
        super().process_end(end, thetex)
        s = r'\end{' + end + '}'
        return self.__remap(s)
    #
    def process_macro(self, tok, thetex):
        macroname = str(tok.macroName)
        obj = thetex.ownerDocument.createElement(macroname)
        s = tok.source
        if s and s[-1] == ' ':
            s = s[:-1]
        if s in (r'\(', r'\['):
            e = '\\' + macros_begin_end[tok.macroName]
            s +=  self.__recurse(e, e, thetex)
            #print('tokenized this ',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
        # it is better not to parse certain macros
        if not isinstance(obj, (FontSelection.TextCommand, DimenCommand, StartSection)) and\
           macroname not in ('emph', 'footnote'):
            obj.parse(thetex)
            s += obj.argSource
            #s = re.sub(" +", ' ',s)
        return self.__remap(s)
    #
    def process_comment(self, comment, thetex):
        comment = comment.rstrip() # remove newline
        return self.__remap('%'+comment) + '\n'

def unsquash_unicode2token(text, helper):
    assert isinstance(text,str)
    tmap = helper.unicode_map
    k2t = helper.key2text
    for k in tmap:
        u = k2t(k)
        t = tmap.get(k)
        if t:
            text = text.replace(u,t)
        else:
            logger.error('Key %r Value %r',k,t)
    return text

def squash_latex(inp : io.IOBase, out : io.IOBase, options : dict, helper=None):
    " transforms LaTeX file"
    if helper is None:
        helper = squash_helper_base()
    #
    assert isinstance(inp, io.IOBase)
    assert isinstance(out, io.IOBase)
    #
    if False:
        # NOPE log = io.StringIO()
        #import tempfile
        log = tempfile.NamedTemporaryFile()
        plasTeX.Logging.fileLogging(log.name)
    else:
        plasTeX.Logging.disableLogging()
    #
    thetex = TeX()
    thetex.input(inp, Tokenizer=TokenizerPassThru.TokenizerPassThru)
    # FIXME it is only useful for the token2unicode machinery 
    ColDoc.utils.TeX_add_packages(thetex, options)
    #
    itertokens = thetex.itertokens()
    helper.itertokens = itertokens
    helper.options = options
    helper.input_filename = getattr(inp,'name', '<unnamed_stream>')
    squash_recurse(out, thetex, itertokens, options, helper)
    if helper.stack :
        logger.warning('squash_latex : file %r : unterminated group, stack is %r', helper.input_filename, helper.stack)
    return helper

def process_helper_command(cmds, out, default_string):
    if cmds is None:
        out.write(default_string)
        return []
    elif isinstance(cmds,str):
        out.write(cmds)
        return []
    else:
        if isinstance(cmds,(list,tuple)):
            cmds = iter(cmds)
        r = []
        try:
            while True:
                c = next(cmds)
                if c == helper_command.WRITE:
                    out.write(next(cmds))
                elif c in ( helper_command.POPSTACK, helper_command.NORECURSE):
                    r.append(c)
                else:
                    raise NotImplementedError(repr(c))
        except StopIteration:
            pass
        return r
    logger.warning('Unprocessed command %r %r',cmds,type(cmds))
    return []


def squash_recurse(out, thetex, itertokens, options, helper, popmacro=None):
    for tok in itertokens:
        # detect $ and $$
        if isinstance(tok, TokenizerPassThru.MathShift):
            tok = '$'
            try:
                d = next(itertokens)
                if isinstance(d, TokenizerPassThru.MathShift):
                    #print(' $$ ')
                    tok = '$$'
                else:
                    #print(' $ ')
                    thetex.pushToken(d)
            except StopIteration:
                #print(' $ ')
                pass
        #
        if isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
            macroname = str(tok.macroName)
            if macroname == 'begin':
                begin = thetex.readArgument(type=str)
                if begin in options.get("verbatim_environment",['verbatim']):
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
                        logger.warning('squash_recurse : file %r : premature end of \\begin{%s}', thetex.filename, begin)
                else:
                    r = helper.process_begin(begin, thetex)
                    r = process_helper_command(r, out, '\\begin{'+begin+'}')
                    if  helper_command.NORECURSE not in r:
                        squash_recurse(out, thetex, itertokens, options, helper, 'E_'+begin)
                    if  helper_command.POPSTACK in r: return
            elif macroname == 'end':
                end = thetex.readArgument(type=str)
                r = helper.process_end(end,thetex)
                r = process_helper_command(r, out, ('\\end{'+end+'}'))
                if  helper_command.POPSTACK in r: return
                if ('E_'+end) != popmacro:
                    logger.warning("squash_recurse : file %r : expected to end on %r ended by end %r ",
                                   thetex.filename, popmacro, 'E_'+end)
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
                r = helper.process_macro(tok,thetex)
                s = tok.source
                if s and s[-1] == ' ':
                    s = s[:-1]
                r = process_helper_command(r, out, s)
                if macroname in macros_begin_end and helper_command.NORECURSE not in r:
                    end = macros_begin_end[macroname]
                    helper.stack_push('\\'+end)
                    squash_recurse(out, thetex, itertokens, options, helper, '\\'+end)
                elif ('\\'+macroname) == popmacro:
                    helper.stack_pop('\\'+macroname)
                    return macroname
                elif macroname in macros_begin_end.values():
                    logger.warning('file %r : disaligned recursion, got unexpected token %r (was expection %r), will try to pop it',
                                   helper.input_filename, macroname, popmacro)
                    helper.stack_pop('\\'+macroname)
                # TODO do not alter preamble in main_file
        elif isinstance(tok, TokenizerPassThru.Comment):
            r = helper.process_comment(str(tok.source),thetex)
            r = process_helper_command(r, out, '%'+tok.source)
            if  helper_command.POPSTACK in r: return
        else:
            r = helper.process_token(tok, thetex, tok == popmacro)
            if not isinstance(tok,str):
                tok = tok.source
            r = process_helper_command(r, out, tok)
            if tok == popmacro :
                return
            elif  (helper_command.NORECURSE not in r) and tok in ('$','$$'):
                squash_recurse(out, thetex, itertokens, options, helper, tok)
            if  helper_command.POPSTACK in r: return


#############################

import io

def reparse_metadata(inp, metadata, blobs_dir, options):
    " reparse metadata of LaTeX file"
    #
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

if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == 'dedollarize':
        helper=squash_modernize_dollars()
        squash_latex(open(sys.argv[2]),sys.stdout,{},helper)
 
