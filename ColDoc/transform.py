#!/usr/bin/env python3

""" the processor
 transforms LaTeX according to rules and tasks
 
 dedollarize [FILE]
    change $...$ to \(...\) and $$...$$ to \[...\]

"""

############## system modules

import  sys, os, io, re, json, pickle, enum, tempfile, unicodedata, subprocess, inspect
import itertools, copy, string, argparse, importlib, shutil, pathlib, copy
import os.path
from os.path import join as osjoin

def _(s):
    "mark translatable strings; no attempt is made to translate them, since this is a library"
    return s

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

from ColDoc import config

import ColDoc.utils
from ColDoc.classes import MetadataBase

try:
    import unicode2latex
except ImportError:
    logger.warning('Please install `unicode2latex` ')
    latex2unicodemath = {}
    latexaccents2unicode = {}
    latex2greek = {}
else:
    latex2unicodemath = unicode2latex.math_latex2unicode
    latexaccents2unicode = unicode2latex.accents_latex2unicode
    latex2mathgreek = unicode2latex.greek_latex2unicode

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

def get_latex_filters():
    latex_filters = []
    for a in dir(ColDoc.transform):
        f = getattr(ColDoc.transform, a)
        if not inspect.isclass(f):
            continue
        act = getattr(f, 'active_in_GUI', True)
        if a.startswith('filter_'):
            latex_filters.append((a, a[7:].replace('_',' ') , getattr(f,'__doc__',''), act, f))
        if a.startswith('squash_helper_') and getattr(f,'present_to_GUI', False):
                latex_filters.append((a, a[14:].replace('_',' ') , getattr(f,'__doc__',''), act, f))
    return latex_filters

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
    def __init__(self, thetex=None, itertokens=None, options={}, input_filename=None, errors = None):
        self.thetex = thetex
        self.itertokens = itertokens
        self.options = options
        self.input_filename = input_filename
        # a list of pairs (s,a) where s is an error string that can be translate before rendering,
        # and then after translations can be formatted: all this using  (_(s) % a)
        # see https://docs.djangoproject.com/en/4.0/topics/i18n/translation/
        self.errors = errors if errors is not None else []
    #
    def process_macro(self, tok):
        return None
    def process_begin(self, begin):
        return None
    def process_end(self, end):
        return None
    def process_comment(self, comment):
        return None
    def process_token(self, tok, is_ending):
        return None

class squash_helper_stack(squash_helper_base):
    "manages the stack"
    def __init__(self, *v, **k):
        self.__stack = []
        super().__init__(*v, **k)
    #
    def process_begin(self, begin):
        self.stack_push('E_'+begin)
    #
    def process_end(self, end):
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

class squash_helper_dedollarize(squash_helper_stack):
    " change $...$ to \(...\) and $$...$$ to \[...\] "
    remap = {
        ('$',False) : '\(',
        ('$',True) : '\)',
        ('$$',False) : '\[',
        ('$$',True) : '\]',
    } 
    present_to_GUI = True
    def process_token(self, tok, is_ending):
        if tok in ('$','$$'):
            k = tok, is_ending
            return self.remap[k]
        return tok



class filter_accents_to_unicode(object):
    ' Convert accents, e.g.: \'e  → é , \`a  → à , \"u  →  ü '
    active_in_GUI = True
    def __init__(self,itertokens, thetex, errors = None):
        self.itertokens = itertokens
        self.thetex = thetex
        self.errors = errors if errors is not None else []
    def __iter__(self):
      try:
        while True:
            tok = next(self.itertokens)
            if not isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                yield tok
            else:
                m = tok.macroName
                if m not in latexaccents2unicode:
                    yield tok
                else:
                    s = self.thetex.readArgument(type=str)
                    if len(s) != 1:
                        logger.warning('argument of accent %r should not be %r', m, s)
                        self.errors.append(( _('argument of accent %(accent)r should not be %(value)r'), {'accent':m,'value':s}))
                    c = s[:1] + chr(latexaccents2unicode[m])
                    c = unicodedata.normalize('NFC', c)
                    yield plasTeX.Tokenizer.Letter(c)
                    for c in s[1:]:
                        yield plasTeX.Tokenizer.Letter(c)
      except StopIteration:
        pass
#####################################




class filterdict(object):
    def __init__(self, itertokens, thetex, errors = None, update = None):
        " the `update` parameter is a dict { macro : unicode } that can be used to override part of the transform"
        self.itertokens = itertokens
        self.thetex = thetex
        if update:
            self.update(update)
        self.errors = errors if errors is not None else []
    #
    def __iter__(self):
        try:
            while True:
                tok = next(self.itertokens)
                if not isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                    yield tok
                else:
                    m = '\\' + tok.macroName
                    c = self.D.get(m,-1)
                    if c >= 0 :
                        yield plasTeX.Tokenizer.Letter(chr(c))
                    else:
                        yield tok
        except StopIteration:
            pass
    #
    def update(self, D2):
        " add updates to the filter mapping"
        self.D = copy.copy(self.D)
        self.D.update(D2)

class filter_math_to_unicode(filterdict):
    r' Convert math macros to Unicode symbols, e.g.: \int  → ∫ '
    D = latex2unicodemath
    active_in_GUI = False
    #mychr = chr

class filter_greek_to_unicode(filterdict):
    r' Convert math macros to greek symbols, e.g.: \alpha  → α '
    #mychr = lambda x : x
    active_in_GUI = False
    D = latex2mathgreek

################################################

class squash_helper_accents_to_unicode(squash_helper_stack):
    def process_macro(self, tok):
        #print('tok  '+tok.macroName+'\n')
        m = tok.macroName
        if m in latexaccents2unicode:
            s = self.thetex.readArgument(type=str)
            if len(s) != 1:
                logger.warning('argument of accent %r should not be %r', m, s)
                self.errors.append(( _('argument of accent %(accent)r should not be %(value)r'), {'accent':m,'value':s}))
            s = s[:1] + chr(latexaccents2unicode[m]) + s[1:]
            s = unicodedata.normalize('NFC', s)
            return s


class squash_input_uuid(squash_helper_stack):
    " replaces \\input and similar with placeholders; delete comments"
    def __init__(self, blobs_dir, blob, options, load_uuid=None, **k):
        self.all_inputs = []
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
        #
        self.lang = k.pop('lang','und')
        self.allowed_blob_names = [ (a+'_'+self.lang) for a in  k.pop('allowed_blob_names',['blob']) ]
        #
        super().__init__(options = options, **k)
    #
    def process_macro(self, tok):
        macroname = str(tok.macroName)
        if macroname in (self.input_macros + self.input_macros_with_parameters):
            argSource = ''
            if macroname in self.input_macros_with_parameters:
                for spec in '*','[]',None:
                    ignore, s = self.thetex.readArgumentAndSource(spec=spec)
                    if spec is None:
                        inputfile = s[1:-1]
                    else:
                        argSource += s
            else:   
                inputfile = self.thetex.readArgument(type=str)
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
                if os.path.isabs(inputfile):
                    s = _('Macro \\%(macroname)s %(argSource)s {%(inputfile)r}  points to an absolute filename')
                    locals_ = copy.copy(locals())
                    logger.warning(s % locals_)
                    self.errors.append(( s, locals_))
                try:
                    uuid, blob = ColDoc.utils.file_to_uuid(inputfile, self.blobs_dir)
                    # this checks if uuid is valid
                    ColDoc.utils.uuid_to_int(uuid)
                except Exception as error:
                    s =  _('Macro \\%(macroname)s %(argSource)s {%(inputfile)r} could not be parsed: %(error)r')
                    locals_ = copy.copy(locals())
                    logger.warning(s % locals_)
                    self.errors.append(( s, locals_))
                    placeholder += '\\' + macroname + argSource + '{' + inputfile + '}'
                    self.all_inputs.append(( macroname, argSource, inputfile, None, None))
                    continue
                if blob is None:
                    s = _('Macro \\%(macroname)s %(argSource)s {%(inputfile)r} does not point to a file')
                    locals_ = copy.copy(locals())
                    logger.warning(s % locals_)
                    self.errors.append(( s,locals_))
                else:
                    blob_base, blob_ext = os.path.splitext(blob)
                    if blob_base not in self.allowed_blob_names:
                        s = _('Macro \\%(macroname)s %(argSource)s {%(inputfile)r} is including an incorrect blob %(blob)s')
                        locals_ = copy.copy(locals())
                        logger.warning( s % locals_)
                        self.errors.append(( s, locals_))
                if inputfile[:5] == 'UUID/':
                    text = uuid
                elif inputfile[:4] == 'SEC/':
                    text = os.path.dirname(inputfile)[4:].replace('_','\_')
                else:
                    logger.debug('while squashing, no good text substitution for inputfile %r uuid %r blob %r', inputfile, uuid, blob)
                    text = uuid
                context = self.stack[-1]  if self.stack else None
                if uuid in self.back_map:
                    self.errors.append( ( _('UUID %(uuid)r is input more than once'), {'uuid':uuid} ) )
                self.back_map[uuid] = macroname, inputfile, context
                self.all_inputs.append(( macroname, argSource, inputfile, uuid, blob))
                #
                if self.load_uuid is not None:
                    child = optarg = None
                    try:
                        child = self.load_uuid(uuid)
                        if config.ColDoc_add_env_when_squashing and child and child.environ in config.ColDoc_environments_sectioning:
                            optarg = json.loads(child.optarg)
                            optarg[0] = '*'
                            placeholder +=  '\\' + child.environ + ''.join(optarg)
                    except:
                        logger.exception('For uuid %r child %r optarg %r ', uuid, child, optarg)
                    if child is None:
                        a = _('Macro %(macroname)r %(argSource)r %(inputfile)r references a non-existant UUID %(uuid)r')
                        locals_ = copy.copy(locals())
                        self.errors.append( (a,locals_) )
                        logger.warning( a % locals_)
                placeholder += (r'\uuidplaceholder{' + uuid + '}{' + text + '}')
            return placeholder
        else:
            return None
    #
    def process_comment(self, comment):
        "deletes comments"
        return '%\n'

class squash_helper_reparse_metadata(squash_input_uuid):
    "reparse metadata"
    def __init__(self, blobs_dir, metadata, options, *v, **k):
        self.metadata_command = options['metadata_command']
        self.metadata = []
        super().__init__(blobs_dir, metadata, options, *v, **k)
    #
    def process_macro(self, tok, environ=None):
        macroname = str(tok.macroName)
        r = super().process_macro(tok)
        if r is not None:
            return r
        if macroname not in self.metadata_command:
            return None
        # keep this in sync with ColDoc.blob_inator, around line 1060
        obj = self.thetex.ownerDocument.createElement(macroname)
        self.thetex.currentInput[0].pass_comments = False
        ## FIXME why is this attribute not there...
        if hasattr(obj,'nargs'):
            N=obj.nargs
        else:
            logger.debug('nargs wrong for '+repr(obj))
            N = 1
        args = [ self.thetex.readArgumentAndSource(type=str)[1] for j in range(N)]
        #obj.parse(self.thetex)
        self.thetex.currentInput[0].pass_comments = True
        logger.info('metadata %r  %r' % (macroname,args))
        #
        a = '' if not self.stack else ('S_'+self.stack[-1]+'_')
        for j in args:
            j =  j.translate({10:32})
            self.metadata.append((a+'M_'+macroname,j))

class squash_helper_token2unicode(squash_helper_stack):
    " replaces all LaTeX with unicode placeholders, and back (used to protect LaTeX during translations) "
    present_to_GUI = True
    def __init__(self, *v, **k):
        self.counter = 0
        self.token_map = OrderedDict()
        self.unicode_map = OrderedDict()
        super().__init__(*v, **k)
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
    def __recurse(self, env_from, env_upto):
        basehelper = squash_helper_stack()
        basehelper.stack_push(env_from)
        basehelper.input_filename = 'SUB ' + str(self.input_filename)
        newout = io.StringIO()
        #print('recurse up to ',env_upto)
        squash_recurse(newout, self.thetex, self.itertokens, self.options, basehelper, env_upto)
        #print('recursed ended up to ',env_upto)
        s = newout.getvalue()
        #s = re.sub(" +", ' ',s)
        return s
    #
    def process_begin(self, begin):
        super().process_begin(begin)
        s = r'\begin{' + begin + '}'
        obj = self.thetex.ownerDocument.createElement(begin)
        if obj.mathMode:
            obj.parse(self.thetex)
            s += obj.argSource
            s += self.__recurse('E_'+begin, 'E_'+begin)
            super().process_end(begin)
            #print('parsing math',begin,'got',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
        return self.__remap(s)
    #
    def process_token(self, tok, is_ending):
        if tok in ('$','$$'):
            if is_ending:
                logger.warning(' problema 32kbgve9w8')
            s = tok +  self.__recurse(tok,tok)
            #print('tokenized dollars ',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
    #
    def process_end(self, end):
        super().process_end(end)
        s = r'\end{' + end + '}'
        return self.__remap(s)
    #
    def process_macro(self, tok):
        macroname = str(tok.macroName)
        obj = self.thetex.ownerDocument.createElement(macroname)
        s = tok.source
        if s and s[-1] == ' ':
            s = s[:-1]
        if s in (r'\(', r'\['):
            e = '\\' + macros_begin_end[tok.macroName]
            s +=  self.__recurse(e, e)
            #print('tokenized this ',repr(s))
            return (helper_command.WRITE, self.__remap(s), helper_command.NORECURSE)
        # it is better not to parse certain macros
        if not isinstance(obj, (FontSelection.TextCommand, DimenCommand, StartSection)) and\
           macroname not in ('emph', 'footnote'):
            obj.parse(self.thetex)
            s += obj.argSource
            # inside the macro arguments, plasTeX will add a space
            s = re.sub(" +", ' ',s)
        return self.__remap(s)
    #
    def process_comment(self, comment):
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

def squash_latex(inp : io.IOBase, out : io.IOBase, options : dict,
                 helper=None, filters = []):
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
    for f in filters:
        # passing helper.errors makes sure that all errors are recorded into it
        itertokens = iter(f(itertokens, thetex, errors = helper.errors))
    #
    helper.thetex = thetex
    helper.itertokens = itertokens
    helper.options = options
    if helper.input_filename is None:
        helper.input_filename = getattr(inp,'name', '<unnamed_stream>')
    squash_recurse(out, thetex, itertokens, options, helper)
    if getattr(helper, 'stack', []):
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
                    r = helper.process_begin(begin)
                    r = process_helper_command(r, out, '\\begin{'+begin+'}')
                    if  helper_command.NORECURSE not in r:
                        squash_recurse(out, thetex, itertokens, options, helper, 'E_'+begin)
                    if  helper_command.POPSTACK in r: return
            elif macroname == 'end':
                end = thetex.readArgument(type=str)
                r = helper.process_end(end)
                r = process_helper_command(r, out, ('\\end{'+end+'}'))
                if  helper_command.POPSTACK in r: return
                if ('E_'+end) != popmacro:
                    logger.warning("squash_recurse : file %r : expected to end on %r ended by end %r , not returning ",
                                   thetex.filename, popmacro, 'E_'+end)
                else:
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
                r = helper.process_macro(tok)
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
            r = helper.process_comment(str(tok.source))
            r = process_helper_command(r, out, '%'+tok.source)
            if  helper_command.POPSTACK in r: return
        else:
            r = helper.process_token(tok, tok == popmacro)
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

def reparse_metadata(inp, metadata, lang, blobs_dir, options, load_uuid=None):
    " reparse metadata of LaTeX file"
    #
    if False:
        # NOPE log = io.StringIO()
        #import tempfile
        log = tempfile.NamedTemporaryFile()
        plasTeX.Logging.fileLogging(log.name)
        print(log.name)
    else:
        plasTeX.Logging.disableLogging()
    #
    ## TODO creates more problem than it solves
    #if not os.path.isabs(inp): inp = osjoin(blobs_dir, inp)
    ##
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
    inp_f = open(inp)
    thetex.input(inp_f, Tokenizer=TokenizerPassThru.TokenizerPassThru)
    out = io.StringIO()
    itertokens = thetex.itertokens()
    #
    helper = squash_helper_reparse_metadata(blobs_dir, metadata, options,
                                            thetex=thetex, itertokens=itertokens, load_uuid=load_uuid, lang=lang)
    from ColDoc.latex import environments_we_wont_latex
    if metadata.environ not in environments_we_wont_latex:
        helper.input_macros_with_parameters += options['split_graphic']
    #
    squash_recurse(out, thetex, itertokens, options, helper)
    #
    inp_f.close()
    #
    a = osjoin(os.path.dirname(inp),'.back_map.pickle')
    f = open(a,'wb')
    pickle.dump(helper.back_map,f)
    f.close()
    a = osjoin(os.path.dirname(inp),'.input_map_'+lang+'.pickle')
    with open(a,'wb') as f:
        pickle.dump(helper.all_inputs,f)
    #
    return helper.back_map, helper.metadata, helper.errors

if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print(__doc__)
        sys.exit(0)
    #
    if sys.argv[1] == 'dedollarize':
        helper=squash_helper_dedollarize()
        squash_latex(open(sys.argv[2]),sys.stdout,{},helper)
    #
    if sys.argv[1] == 'accents_to_unicode':
        helper=squash_helper_accents_to_unicode()
        inp = io.StringIO(sys.argv[2])
        squash_latex(inp,sys.stdout,{},helper)
