#!/usr/bin/env python3

""" the Blob Inator
splits the input into blobs

(this version is not integrated with Django)
"""

default_metadata = [ 'label', 'uuid', 'index', 'author', 'date',
                                    'title', 'ref', 'eqref', 'pageref', 'cite' ]
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

from ColDoc.classes import MetadataBase, DuplicateLabel

from ColDoc.latex import ColDoc_latex_engines


#########################################################################
from ColDoc import TokenizerPassThru

import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base

from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Packages import amsthm , graphicx

#import plasTeX.Base.LaTeX as LaTeX
#import plasTeX.Base.LaTeX.Environments as Environments

# non funziona
#plasTeX.TeX.Tokenizer = TokenizerPassThru.TokenizerPassThru


######################################################################



class named_stream(io.StringIO):
    """ stream with a filename attached, and metadata; data will be written by 'writeout' method
      the file will be written in a new UUID under `basepath`
    """
    #
    _re_spaces_ =  re.compile('^[ \t\n]+$')
    _default_rstrip = ColDoc_blob_rstrip
    _default_write_UUID = ColDoc_write_UUID
    _do_not_write_uuid_in = ColDoc_do_not_write_uuid_in
    #
    # _coldoc and _basepath are passed to _metadata_class
    _default_coldoc = None
    _default_basepath = None
    _metadata_class = MetadataBase # <- this must be overridden
    _private = []
    _authors = []
    #
    def __init__(self, environ ,
                lang = ColDoc_lang, extension = '.tex',
                early_UUID = ColDoc_early_UUID,
                parentUUID = None, parent = None,
                basepath=None, coldoc = None,
                *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store parameters
        if basepath is None : basepath = self._default_basepath
        assert os.path.isdir(basepath)
        self._basepath = basepath
        if coldoc is None : coldoc = self._default_coldoc
        self._coldoc = coldoc
        #
        self._environ = environ
        self._extension = extension
        self._lang = lang
        # prepare internal stuff
        self._was_written = False
        self._uuid = None
        self._filename = None
        self._dir = None
        self._symlink_dir = None
        self._symlink_files = set()
        self.grouping_depth = 0
        # save from gc, for __del__ method
        self._sys = sys
        self._open = open
        self._logger = logger
        # set up UUID
        if early_UUID:
            self._find_unused_UUID()
        # prepare metadata
        self._metadata = self._metadata_class(basepath=basepath,coldoc=coldoc)
        self.add_metadata('environ', environ)
        self.add_metadata('extension', extension)
        self.add_metadata('lang', lang)
        #
        logger.debug("new %r",self)
        #
        if parent is not None:
            #if parentFile is None : parentFile = parent.filename
            if parentUUID is None : parentUUID = parent.uuid
        #if parentFile:
        #    self.add_metadata('parent_file', parentFile)
        if parentUUID:
            self.add_metadata('parent_uuid', parentUUID)
        elif environ != 'main_file':
            logger.critical('blob %r has parent %r ?' % (self,parent))
        #
        self.obliterated = False
    #
    def __repr__(self):
        return ('<named_stream(basepath=%r, coldoc=%r, uuid=%r, environ=%r, lang=%r, extension=%r)>' % \
               (self._basepath,self._coldoc,self._uuid,self._environ,self._lang,self._extension))
    #
    def _find_unused_UUID(self):
        "set `filename` and `metadata_filename`, using a new UUID"
        filename = None
        while not filename:
            u = new_uuid(blobs_dir=self._basepath)
            d = uuid_to_dir(u, blobs_dir=self._basepath, create=True)
            filename = osjoin(d, 'blob_' + self._lang + self._extension)
            if os.path.exists( osjoin(self._basepath, filename) ):
                logger.warn(' output exists %r, trying next UUID' % filename)
                filename = None
        assert not os.path.isabs(filename)
        assert not os.path.exists ( osjoin(self._basepath, filename) )
        self._filename = filename
        self._dir = d
        self._uuid = u
    @property
    def lang(self):
        return self._lang
    @property
    def environ(self):
        return self._environ
    @property
    def uuid(self):
        return self._uuid
    #@uuid.setter
    #def symlink_uuid(self, u):
    ##    u = str(u)
    # #   self._uuid = u
    #    d = uuid_to_dir(u)
    #    if not os.path.isdir(d): os.mkdir(d)
    #    self._filename = osjoin(d,'tex_' + EDB_lang + '.tex')
    ##    self._metadata_file = osjoin(uuid_to_dir(u),'metadata')
    #    print(self._filename)
    @property
    def symlink_dir(self):
        "a symlink (relative to `basepath`) pointing to the directory where the content will be saved"
        return self._symlink_dir
    @symlink_dir.setter
    def symlink_dir(self, symlink_dir):
        """ set the symlink (relative to `basepath`)
        """
        assert not os.path.isabs(symlink_dir)
        self._symlink_dir = symlink_dir
    #
    @property
    def symlink_files(self):
        "a `set` of symlinks (relative to `basepath`) pointing to the blob"
        return self._symlink_files
    @symlink_files.setter
    def symlink_files(self, symlink_file):
        " please use `symlink_file_add`"
        raise NotImplementedError(" please use `symlink_file_add`")
    #
    def symlink_file_add(self, symlink_file):
        """ add a name for a symlink (relative to `basepath`) for this blob
        """
        if '..' in symlink_file.split(os.path.sep):
            logger.warning(" will not create symlink with '..' in it: %r",symlink_file)
        elif  os.path.isabs(symlink_file):
            logger.warning(" will not create absolute symlink: %r",symlink_file)
        else:
            self._symlink_files.add(symlink_file)
    #
    @property
    def filename(self):
        "the filename relative to `basepath` where the content will be saved"
        return self._filename
    @filename.setter
    def filename(self, filename):
        """ set the filename (relative to `basepath`) where the content will be saved ;
            this changes also the metadata filename.
            Please use `self.symlink_dir` and not this call.
        """
        logger.warn("Please do not use self.filename = %r, use self.symlink " % (filename,))
        assert not os.path.isabs(filename)
        self._filename = filename
        self._dir = os.path.dirname(filename)
    #
    def __len__(self):
        return len(self.getvalue())
    def add_metadata(self,T,E, braces=False):
        """ The parameter `braces` dictates if `E` will be enclosed in {};
        `braces` may be `True`,`False` or `None` (which means 'autodetect')
        """
        assert not self._was_written
        assert isinstance(E,str)
        assert E
        assert braces in (True,False,None)
        E = E.translate({10:32})
        if braces is False or \
           ( E[0] == '{' and E[-1] == '}' and braces is None ):
            self._metadata.add(T, E)
        else:
            self._metadata.add(T, '{'+E+'}')
    #
    def rstrip(self):
        """ returns the internal buffer, but splitting the final lines of the buffer,
        as long as they are all whitespace ;
        returns (initial_part, stripped_part) """
        self.seek(0)
        l = self.readlines()
        sp=''
        while l and l[-1] and self._re_spaces_.match( l[-1]) is not None:
            sp = l[-1] + sp
            l.pop()
        return ''.join(l) , sp
    #
    def writeout(self, write_UUID = None, rstrip = None):
        """Writes the content of the file; returns the `filename` where the content was stored,
        relative to `basedir` (using the `symlink_dir` if provided).

        - If `write_UUID` is `True`, the UUID will be written at the beginning of the blob
          (but for `section` blobs: for those it is written by another part of the code)

        - If `write_UUID` is 'auto', the UUID will be not be written in 'section'
          and in any other environ listed in `ColDoc_do_not_write_uuid_in`

        - If `write_UUID` is `False`, no UUID will be written.

        If `rstrip` is `True`, will use `self.rstrip` to strip away final lines of only whitespace
        """
        if self.obliterated:
            logger.warning("Will not write obliterated blob",repr(self))
            return False
        if rstrip is None : rstrip = self._default_rstrip
        if write_UUID is None : write_UUID = self._default_write_UUID
        #
        assert write_UUID in (True,False,'auto')
        if self.environ == 'section' or \
           (write_UUID == 'auto' and self.environ in self._do_not_write_uuid_in):
            write_UUID = False
        elif write_UUID == 'auto':
            write_UUID = True
        if self._filename is None:
            self._find_unused_UUID()
        if self._was_written :
            logger.critical('file %r was already written ' % self._filename)
            return self._filename
        if self.closed :
            logger.error('file %r was closed before writeout' % self._filename)
        if self.grouping_depth:
            logger.warning('some grouping was not closed in %r' % self._filename)
        filename = osjoin(self._basepath, self._filename)
        if True: #len(self.getvalue()) > 0:
            self.flush()
            logger.info("writeout file %r  " % (self._filename,))
            z = self._open(filename ,'w')
            if write_UUID and self.uuid:
                z.write("\\uuid{%s}%%\n" % (self.uuid,))
            if rstrip:
                cnt, tail = self.rstrip()
            else:
                cnt = self.getvalue()
            z.write(cnt)
            z.close()
            #
            if len(cnt) == 0:
                logger.warning('empty blob %r' % self)
            #
            self._metadata.add('uuid',self._uuid)
            if self.environ[:2] == 'E_' and self.environ[2:] in self._private:
                self._metadata.add('access', 'private')
            if self._authors:
                # Django needs to set the `id` before adding authors
                self._metadata.save()
            for j in self._authors:
                self._metadata.add('author', j)
            self._metadata.blob_modification_time_update()
            self._metadata.save()
            #
            r =  self._filename
            # no more messing with this class
            self._was_written = True
            self.close()
            if self._symlink_dir:
                os_rel_symlink(self._dir,self._symlink_dir,basedir=self._basepath,
                               force = True, target_is_directory=True)
                r = osjoin(self._symlink_dir, os.path.basename(filename))
            if self._symlink_files:
                for j in self._symlink_files:
                    os_rel_symlink(r, j ,basedir=self._basepath, force = True,
                                   target_is_directory=False)
            return r
    def __del__(self):
        if not self.obliterated and not self._was_written :
            self._logger.critical('this file was not written %r' % self._filename)
    def obliterate(self):
        self.close()
        uuid = self._uuid
        if uuid is not None:
            if not backtrack_uuid(uuid, blobs_dir=self._basepath,):
                logger.warning("The UUID %r was not used, it is lost",self._uuid)
        self._uuid = None
        # this avoids the warning in __del__ and avoids
        #  that this blob be recorded as a child of its parent, when it is popped
        self.obliterated = True

def new_theorem(a,doc,con):
    " from amsthm.py "
    name = str(a['name'])
    header = a['header']
    star = a['*modifier*'] == '*'
    parent = a['parent']
    shared = a['shared']
    style = doc.userdata.getPath('packages/amsthm/currentstyle')

    ##l = doc.userdata.getPath('packages/amsthm/theorems')
    ##l += [name]

    if star:
        thecounter = None
    else:
        if parent and not shared:
            con.newcounter(name, initial=0, resetby=parent)
            con.newcommand("the"+name, 0,
                                    "\\arabic{%s}.\\arabic{%s}"%(parent,name))
            thecounter = name
        elif shared:
            thecounter = shared
        else:
            thecounter = name
            con.newcounter(name, initial=0)
            con.newcommand("the"+name, 0, "\\arabic{%s}" %name)

    data = {
            'macroName': name,
            'counter': thecounter,
            'thehead': header,
            'thename': name,
            'labelable': True,
            'forcePars': True,
            'thestyle': style
        }
    th = type(name, (amsthm.theoremCommand,), data)
    return th



def is_math_mode(o):
    """ Hints if the object `o` starts a math mode or non-math mode LaTex
        Warning: it is quite primitive"""
    assert isinstance(o, (str,named_stream))
    r = None
    if isinstance(o, str):
        e = o
        l = 'str:'+o
    elif isinstance(o, named_stream):
        e =  o.environ
        l = 'named_stream:'+e
    if e.startswith('E_'):
        e = e[2:]
        if e[-1] == '*':
            e = e[:-1]
        if e in ('math','displaymath','equation','subequations',
                 'eqnarray','split','multiline','array',
                 'gather','align','flalign'):
            r = True
        else:
            r = False
    else:
        # fixme: how to support $$...$$ and $...$ 
        # must check what the plastex parser does...
        if o in ('\\[','\\('):
            r = True
        else:
            r = False
    assert r is not None
    logger.debug("This is %s math: %s", '' if  r else 'not', l )
    return r

class EnvStreamStack(object):
    """ a class that manages a stack of named_stream and LaTeX environments,
    interspersed"""
    def __init__(self):
        self._stack=[]
        self._topstream = None
        self._math_mode = False
    def __repr__(self):
        return ' ==> '.join(repr(r) for r in self._stack)
    def __len__(self):
        return len(self._stack)
    #
    def _set_math_mode(self):
        if self._stack:
            m = is_math_mode(self._stack[-1])
            if m != self._math_mode:
                logger.debug('Exit, now %s math mode', '' if  m else 'not')
            self._math_mode = m
        else:
            self._math_mode = False
    @property
    def math_mode(self):
        "fixme , this is not perfect, it does not deal with \text or \parbox"
        return self._math_mode
    @property
    def top(self):
        " the top element"
        logger.debug(repr(self))
        return self._stack[-1]
    @property
    def topstream(self):
        " the topmost stream"
        return self._topstream
    @property
    def topenv(self):
        "the top environment"
        s = self._stack[-1]
        if isinstance(s,named_stream):
            return s.environ
        return s
    #
    def _set_topstream(self, checknonempty=True):
        self._topstream = None
        for j in reversed(self._stack):
            if isinstance(j,named_stream):
                self._topstream = j
                break
        if checknonempty and self._topstream is None:
            logger.critical('There is no blob to write to! blob_inator crashes!')
            raise RuntimeError('There is no blob to write to!')
    def push(self,o):
        assert isinstance(o, (str,named_stream))
        logger.debug('%r onto %r',o,repr(self))
        m = is_math_mode(o)
        if m != self._math_mode:
            logger.debug('Entering %s math mode', '' if  m else 'not')
        self._math_mode = m
        self._stack.append(o)
        if isinstance(o,named_stream):
            self._topstream = o
    def pop(self, index=-1, add_as_child = True, checknonempty=True):
        """ pops topmost element , or `index` element if given;
        if `add_as_child` and topmost element was a stream,
        write its UUID and filename in metadata of the parent stream"""
        o = self._stack.pop(index)
        logger.debug(repr(self))
        if isinstance(o, named_stream):
            self._set_topstream(checknonempty=checknonempty)
            if add_as_child and self._topstream is not None \
               and isinstance(self._topstream,named_stream) and not o.obliterated:
                if o.uuid is None :
                    logger.warning("Cannot add blob as child, uuid is None: %r",o)
                else:
                    self._topstream.add_metadata('child_uuid',o.uuid)
                #if o.filename:
                #    self._topstream.add_metadata('child_filename',o.filename)
        self._set_math_mode()
        return o
    def pop_str(self, warn=True, stopafter=None):
        " pop strings, until a stream is reached or after popping `stopafter`"
        while self._stack:
            s = self._stack[-1]
            if isinstance(s,str):
                if stopafter is not None and stopafter == s:
                    self._stack.pop()
                    break
                if warn:
                    logger.warning(' environment was not closed: %r' % s)
                self._stack.pop()
            else:
                break
        self._set_math_mode()
        logger.debug(repr(self))
    def pop_stream(self, add_as_child = True):
        " pops the topmost stream, w/o touching the non-stream elements of the stack"
        t = None
        for n,j in enumerate(self._stack):
            if isinstance(j,named_stream):
                t=n
        assert t is not None
        O = self.pop(index=t, add_as_child = add_as_child)
        self._set_math_mode()
        logger.debug(repr(self))
        return O

def blob_inator(thetex, thedocument, thecontext, cmdargs, metadata_class, coldoc):
    use_plastex_parse = True
    blobs_dir=cmdargs.blobs_dir
    shift_eol=True
    # normalize input file path
    input_file = os.path.abspath(cmdargs.input_file)
    input_basedir = os.path.dirname(input_file)
    #
    disaster_recovery = False # <- makes debugging more difficult
    #
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    in_preamble = False
    #
    ### unfortunately Django is too complex...
    #assert issubclass(metadata_class, MetadataBase)
    #
    ## to avoid giving these parameters to named_stream() each time
    named_stream._metadata_class = metadata_class
    named_stream._default_basepath = blobs_dir
    named_stream._default_coldoc = coldoc
    named_stream._authors = cmdargs.author
    named_stream._private = cmdargs.private_environment
    #
    # map to avoid duplicating the same input on two different blobs;
    # each key is converted to an absolute path relative to `blobs_dir`;
    # the value is a pair `(O,U)`
    # with `O` being either the `named_stream` or a path relative to `blobs_dir`
    # and `U` being the UUID
    file_blob_map = absdict(basedir = input_basedir, loggingname='file_blob_map')
    #
    def write_special_EOF():
        a=io.StringIO()
        a.write('\\'+specialblobinatorEOFcommand)
        a.seek(0)
        a.name='specialblobinatorEOFcommand'
        thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
        del a
    thetex.input(open(cmdargs.input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    stack = EnvStreamStack()
    output = named_stream('main_file')
    output.add_metadata('original_filename',os.path.basename(input_file))
    output.add_metadata('original_absolute_filename',input_file)
    file_blob_map[input_file] = output,output.uuid
    output.symlink_file_add('main.tex')
    if cmdargs.symlink_input:
        output.symlink_file_add(os.path.basename( input_file))
    stack.push(output)
    del output, input_file
    def input_it(r):
        t = stack.topstream
        t.write('\\input{%s}' % (r,))
        if ColDoc_commented_newline_after_blob_input:
            t.write('%\n')
    def pop_paragraph():
        if stack.topstream.environ == 'paragraph':
            O = stack.topstream
            l = len(O)
            assert cmdargs.split_paragraph is not None
            if l < cmdargs.split_paragraph:
                # do not record as a child
                stack.pop_stream(add_as_child = False)
                logger.info('paragraph too short (len == %d), zip %r into %r',l,O,stack.topstream)
                stack.topstream.write(O.getvalue())
                O.obliterate()
            else:
                r = stack.pop_stream().writeout()
                input_it(r)
    def pop_section():
        # do not destroy stack, stack.pop_str()
        if stack.topstream.environ == 'section':
            r = stack.pop_stream().writeout()
            input_it(r)
        # do not destroy stack, stack.pop_str()
    def log_mismatch(beg,end):
        if beg[:2] == 'E_':
            beg = '\\begin{' + beg[2:] + '}'
        else:
            beg = 'blob `' + beg + '`'
        if end[:2] == 'E_':
            end = '\\end{' + end[2:] + '}'
        else:
            end = 'blob `' + end + '`'
        logger.error(' LaTeX Error: %s ended by %s ' % (beg,end))
    ###################
    def parse_biblio_usepackage(macroname,topstream):
        ext = {'bibliography':'.bib','usepackage':'.sty'}[macroname]
        thetex.currentInput[0].pass_comments = False
        if macroname == 'usepackage':
            opt = thetex.readArgument('[]',type=str)
            if not opt:
                opt = ''
            else:
                opt = '['+opt+']'
        else:
            opt = ''
        arg = thetex.readArgument(type=str)
        thetex.currentInput[0].pass_comments = True
        arg = arg.split(',')
        if opt and len(arg)>1:
            logger.warning('Cannot cope with %r %r %r',macroname,opt,arg)
        outlist = []
        for fil in arg:
            if  fil.endswith(ext):
                logger.warning('\\%s{%s} with extension',macroname,fil)
                fil = fil[:-len(ext)]
            absinputfile = osjoin(input_basedir,fil+ext)
            if not os.path.exists(absinputfile):
                absinputfile = None
            ## TODO copying packages is quite difficult
            #else:
            #    try:
            #        inputfile = thetex.kpsewhich(a)
            #    except:
            #        logger.exception('kpsewhich failed on %r',a)
            #    else:
            #        # copy only stuff inside the home directory
            #        if not inputfile.startswith(os.path.expanduser('~')):
            #            inputfile = None
            
            if absinputfile is None:
                topstream.write('\\'+macroname+opt+'{'+fil+'}')
            else:
                uuid = new_uuid(blobs_dir=blobs_dir)
                do = uuid_to_dir(uuid, blobs_dir=blobs_dir, create=True)
                fo = osjoin(do,'blob')
                fm = metadata_class(basepath=blobs_dir,coldoc=coldoc)
                fm.add('uuid', uuid)
                fm.add('environ',  macroname)
                fm.add('extension',ext)
                fm.add('original_filename', fil)
                fm.add('original_command', '\\'+macroname+'{'+fil+'}')
                fm.add('parent_uuid', stack.topstream.uuid)
                # alas we cannot split 'bibliography'
                outlist.append(fo)
                a,b=absinputfile,osjoin(blobs_dir,fo)+ext
                logger.debug('Copy %r to %r',a,b)
                shutil.copy(a,b)
                fm.save()
        topstream.write('\\'+macroname+opt+'{'+(','.join(outlist))+'}')
    #############################################################
    #
    itertokens = thetex.itertokens()
    n=0
    try:
        for tok in itertokens:
            n += len(tok.source)
            if not in_preamble and isinstance(tok, plasTeX.Tokenizer.Letter) \
               and stack.topstream.grouping_depth == 0 and cmdargs.split_paragraph is not None \
               and stack.topenv in ('section','main_file','input','include'):
                stack.push(named_stream('paragraph', parent=stack.topstream))
                stack.topstream.write(str(tok))
            elif isinstance(tok, TokenizerPassThru.Comment):
                a = tok.source
                stack.topstream.write('%'+a)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                macroname = str(tok.macroName)
                if cmdargs.split_paragraph is not None and \
                   macroname == 'par':
                    pop_paragraph()
                if macroname == 'documentclass':
                    in_preamble = True
                    obj = Base.documentclass()
                    thetex.currentInput[0].pass_comments = False
                    a = obj.parse(thetex)
                    thetex.currentInput[0].pass_comments = True
                    # implement obj.load(thetex, a['name'], a['options'])
                    thecontext.loadPackage(thetex, a['name']+'.cls',
                                           a['options'])
                    stack.topstream.write(obj.source)
                    stack.topstream.add_metadata('documentclass',a['name'])
                    if a['options'] :
                        j = ','.join(a['options'].keys())
                        stack.topstream.add_metadata('documentclassoptions',j)
                    if cmdargs.split_preamble:
                        stack.push(named_stream('preamble', parent=stack.topstream))
                elif cmdargs.split_sections and macroname == 'section':
                    pop_paragraph()
                    pop_section()
                    #obj = Base.section()
                    #obj.parse(thetex)
                    # the above fails, we are not providing the full context to it
                    # so we imitate it, iterating over obj.arguments:
                    thetex.currentInput[0].pass_comments = False
                    argSource = ''
                    for spec in '*','[]',None:
                        output, source = thetex.readArgumentAndSource(spec=spec) #parentNode=obj,name=arg.name,**arg.options)
                        #logger.debug(' spec %r output %r source %r ' % (spec,output,source) )
                        argSource += source
                    thetex.currentInput[0].pass_comments = True
                    name = source[1:-1]
                    n = new_section_nr(blobs_dir = blobs_dir)
                    u = int_to_uuid(n)
                    f = 'SEC/%s_%s' % (u , slugify(name) )
                    logger.info('starting section %r . linked by dir %r' % (name,f))
                    add_child = True
                    if cmdargs.zip_sections:
                        if stack.topstream != stack.top:
                            logger.warning("cannot zip section %r (found inside environment %r)" % (name,stack.topenv))
                        elif stack.topenv == 'section':
                            logger.warning("cannot zip the section %, it is after a previous section in blob %r" %\
                                           (name,stack.topstream))
                        elif len(stack.topstream) > 0:
                            logger.warning("cannot zip section %r , parent blob %r has length %d (try to remove cruft before \\section)" %\
                                           (name,stack.topstream,len(stack.topstream)))
                        else:
                            add_child = False
                    if add_child:
                        stack.push(named_stream('section', parent=stack.topstream))
                    stack.topstream.symlink_dir = f
                    stack.topstream.add_metadata('section',argSource, braces=False)
                    stack.topstream.write('\\section'+argSource)
                    if stack.topstream.uuid and cmdargs.add_UUID:
                        stack.topstream.write("\\uuid{%s}" % (stack.topstream.uuid,))
                elif cmdargs.split_all_theorems and macroname == 'newtheorem':
                    obj = amsthm.newtheorem()
                    thetex.currentInput[0].pass_comments = False
                    obj.parse(thetex)
                    thetex.currentInput[0].pass_comments = True
                    stack.topstream.write(obj.source)
                    logger.info('adding to splited environments: %r' % obj.source)
                    th = new_theorem(obj.attributes, thedocument, thecontext)
                    name = obj.attributes['name']
                    cmdargs.split_environment.append(name)
                    thecontext.addGlobal(name, th)
                    del th
                elif macroname in ("input","include"):
                    if macroname == "include" and stack.topstream.environ == "section":
                        r = stack.pop_stream().writeout()
                        input_it(r)
                    thetex.currentInput[0].pass_comments = False
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                        # only follow local files
                        #inputfile = thetex.kpsewhich(inputfile)
                    else:
                        inputfile = thetex.readArgument(type=str)
                    thetex.currentInput[0].pass_comments = True
                    inputfileext = inputfile + ('' if inputfile[-4:] == '.tex' else '.tex' )
                    if inputfileext in file_blob_map:
                        O,U = file_blob_map[inputfileext]
                        if not isinstance(O,named_stream):
                            logger.error("the input %r was already parsed as object %r uuid %r ?!?",
                                         inputfile,O,U)
                        elif not O.closed:
                            logger.critical("recursive input: %r as %r", inputfile, O)
                            raise RuntimeError("recursive input: %r as %r" % (inputfile, O))
                        assert O.uuid == U
                        #
                        m = metadata_class.load_by_uuid(O.uuid, basepath=blobs_dir, coldoc=coldoc)
                        m.add('original_filename', inputfile)
                        m.add('parent_uuid',stack.topstream.uuid)
                        m.save()
                        del m
                        logger.warning("duplicate input, parsed once: %r", inputfile)
                        stack.topstream.write('\\%s{%s}' % (macroname,O.filename))
                    else:
                        newoutput = named_stream(macroname + ('_preamble' if in_preamble else ''),
                                                 parent=stack.topstream)
                        newoutput.add_metadata(r'original_filename',inputfile)
                        stack.push(newoutput)
                        if cmdargs.symlink_input:
                            newoutput.symlink_file_add(inputfileext)
                        if not os.path.isabs(inputfile):
                            inputfile = os.path.join(input_basedir,inputfile)
                        if not os.path.isfile(inputfile):
                            inputfile += '.tex'
                        assert os.path.isfile(inputfile), "file does not exist: %r"%(inputfile,)
                        file_blob_map[inputfile] = newoutput, newoutput.uuid
                        del newoutput
                        logger.info(' processing %r ' % (inputfile))
                        write_special_EOF()
                        thetex.input(open(inputfile), Tokenizer=TokenizerPassThru.TokenizerPassThru)
                    del inputfile
                elif macroname == specialblobinatorEOFcommand:
                    pop_paragraph()
                    pop_section()
                    # pops the output when it ends
                    z = stack.pop()
                    r = z.writeout()
                    logger.info('end input, writing %r',r)
                    a=z.environ
                    if a == 'include' and r[-4:] == '.tex':
                        r=r[:-4]
                    if a not in ('input','include','input_preamble','include_preamble','usepackage'):
                        logger.error("the blob %r ends with an unmatched %r",z,a)
                        stack.topstream.write('\\input{%s}' % (r,))
                    else:
                        if a in ('input_preamble','include_preamble'):
                            a = a[:-len('_preamble')]
                        stack.topstream.write('\\%s{%s}' % (a,r))
                    if a == 'input' and ColDoc_commented_newline_after_blob_input:
                        stack.topstream.write('%\n')
                    del r,z,a
                elif macroname  in ('bibliography','usepackage'):
                    parse_biblio_usepackage(macroname,stack.topstream)
                elif not in_preamble and macroname in cmdargs.split_graphic :
                    if macroname == "includegraphics":
                        obj = graphicx.includegraphics()
                        thetex.currentInput[0].pass_comments = False
                        a = obj.parse(thetex)
                        thetex.currentInput[0].pass_comments = True
                        inputfile = a['file']
                        src = obj.source
                        j = src.index('{')
                        cmd = src[:j]
                        del obj, a
                    else:
                        logger.warning('FIXME, should improve parsing of %r',macroname)
                        cmd = src = '\\' + macroname
                        thetex.currentInput[0].pass_comments = False
                        for spec in '*','[]',None:
                            _, s = thetex.readArgumentAndSource(spec=spec)
                            src += s
                            if spec:
                                cmd += s
                            else:
                                inputfile = s[1:-1]
                        thetex.currentInput[0].pass_comments = True
                    assert isinstance(inputfile,str)
                    logger.debug('parsing %r' , cmd+'{'+inputfile+'}')
                    assert not os.path.isabs(inputfile), "absolute path not supported: "+cmd+'{'+inputfile+'}'
                    if inputfile in file_blob_map:
                        O, U = file_blob_map[inputfile]
                        if not isinstance(O,str):
                            logger.critical("the input %r was already parsed as object %r uuid %r",
                                            inputfile,O,U)
                            raise RuntimeError("the input %r was already parsed as object %r uuid %r" %
                                               (inputfile,O,U))
                        m = metadata_class.load_by_uuid(U, basepath=blobs_dir, coldoc=coldoc)
                        m.add('original_filename', inputfile)
                        m.add('original_command', src)
                        m.add('parent_uuid',stack.topstream.uuid)
                        m.add('extension',os.path.splitext(inputfile)[1])
                        m.save()
                        logger.warning("duplicate graphical input, copied once: %r", inputfile)
                        stack.topstream.write(cmd+'{'+O+'}')
                        del cmd,src,m,inputfile
                    else:
                        di,bi = os.path.split(inputfile)
                        bi,ei=os.path.splitext(bi)
                        assert inputfile == osjoin(di,bi+ei)
                        if ei and not os.path.isfile(osjoin(input_basedir,inputfile)):
                            logger.error(' while parsing %r, no  such file: %r' %(src,fi,))
                        # find all interesting files
                        is_graph = False
                        exts = []
                        for j in os.listdir(osjoin(input_basedir,di)):
                            bj,ej = os.path.splitext(j)
                            if bj == bi:
                                exts.append(ej)
                                if ej.lower() in ['','.png','.jpg','.jpeg','.gif','.pdf','.ps','.eps','.tif','.tiff']:
                                    is_graph = True
                        #
                        if not exts :
                            logger.error(' while parsing %r, no files %r.ext were found (for any possible extension `ext`' %\
                                (cmd+'{'+inputfile+'}',osjoin(di,bi)))
                        elif not is_graph:
                            logger.warning(' while parsing %r, no  graphical files %r.ext were found (for extensions `ext` that look like a graphic file' %\
                                (cmd+'{'+inputfile+'}',osjoin(di,bi)))
                        #
                        uuid = new_uuid(blobs_dir=blobs_dir)
                        do = uuid_to_dir(uuid, blobs_dir=blobs_dir, create=True)
                        fo = osjoin(do,'blob')
                        fm = metadata_class(basepath=blobs_dir,coldoc=coldoc)
                        fm.add('uuid', uuid)
                        fm.add('original_filename', inputfile)
                        fm.add('original_command', src)
                        fm.add('parent_uuid', stack.topstream.uuid)
                        # will load the same extension, if specified
                        stack.topstream.write(cmd+'{'+fo+ei+'}')
                        #
                        file_blob_map[inputfile] = fo+ei, uuid
                        file_blob_map[osjoin(di,bi)] = fo, uuid
                        # copy all files with same base, different extensions
                        ext = fii = None
                        for ext in exts:
                            fii = osjoin(di,bi+ext)
                            logger.info(' copying %r to %r' % (fii,fo+ext) )
                            shutil.copy(osjoin(input_basedir,fii),osjoin(blobs_dir,fo+ext))
                            fm.add('extension', ext)
                            if cmdargs.symlink_input:
                                try:
                                    os_rel_symlink(fo+ext,fii,cmdargs.blobs_dir ,
                                                   target_is_directory=False)
                                except:
                                    logger.exception("cannot create symlink %r", fii)
                            #
                            file_blob_map[fii] = fo+ext,uuid
                            #
                        fm.save()
                        del do,fo,fm,exts,cmd,di,bi,ei,ext,fii,src,uuid
                elif macroname == "item":
                    e = stack.topenv
                    if len(e) >= 3 and e[:2] == 'E_' and e[2:] in cmdargs.split_list :
                        r = stack.pop().writeout()
                        logger.info('end item, writing %r',r)
                        stack.topstream.write(' \\input{%s}%%\n\\item ' % (r,))
                        _,source = thetex.readArgumentAndSource('[]')
                        if source:
                            stack.topstream.write(source)
                        stack.push(named_stream(e,parent=stack.topstream))
                        del r
                    else:
                        stack.topstream.write('\\item')
                    del e
                elif macroname == "begin":
                    pop_paragraph()
                    name = thetex.readArgument(type=str)
                    if name == 'document':
                        if not in_preamble:
                            logger.error(' \\begin{document} can only be used in preamble')
                        elif cmdargs.split_preamble:
                            old = stack.pop()
                            assert old.environ == 'preamble', " in preamble, the element %r does not match" % old
                            r = old.writeout()
                            del old
                            os_rel_symlink(r,'preamble.tex', cmdargs.blobs_dir ,
                                           target_is_directory=False, force=True)
                            input_it(r)
                        in_preamble = False
                        if ColDoc_write_UUID:
                            #stack.topstream.write(r'\usepackage{ColDocUUID}')
                            a = osjoin(blobs_dir,'ColDocUUID.sty')
                            if not os.path.exists(a):
                                os.symlink(osjoin(COLDOC_SRC_ROOT,'tex','ColDocUUID.sty'), a)
                            a = osjoin(blobs_dir,'ColDocIfs.sty')
                            if not os.path.exists(a):
                                os.symlink(osjoin(COLDOC_SRC_ROOT,'tex','ColDocIfs.sty'), a)
                    stack.topstream.write(r'\begin{%s}' % name)
                    if in_preamble:
                        logger.info( ' ignore \\begin{%r} in preamble' % (name,) )
                    elif name in cmdargs.verbatim_environment:
                        class MyVerbatim(Base.verbatim):
                            macroName = name
                        obj = MyVerbatim()
                        obj.ownerDocument = thetex.ownerDocument
                        t = obj.invoke(thetex)
                        # the above pushes the \end{verbatim} back on stack
                        next(itertokens)
                        for j in t[1:]:
                            stack.topstream.write(j)
                        stack.topstream.write('\\end{%s}' % name)
                        del obj,j,t
                    elif name in cmdargs.split_environment :
                        obj = thedocument.createElement(name)
                        obj.macroMode = Command.MODE_BEGIN
                        obj.ownerDocument = thedocument
                        source = None
                        if isinstance(obj, amsthm.theoremCommand) or name == 'figure':
                            thetex.currentInput[0].pass_comments = False
                            _,source = thetex.readArgumentAndSource('[]')
                            thetex.currentInput[0].pass_comments = True
                            if source:
                                stack.topstream.write(source)
                        #out = obj.invoke(tex) mangles everything
                        #if out is not None:
                        #    obj = out
                        logger.info( 'will split \\begin{%r}' % (name,) )
                        if shift_eol:
                            t=next(itertokens)
                            while str(t) in ('\n',' '):
                                stack.topstream.write(str(t))
                                t=next(itertokens)
                            thetex.pushToken(t)
                        stack.push(named_stream('E_'+name,parent=stack.topstream))
                        if source:
                            assert source[0] == '[' and source[-1] == ']'
                            stack.topstream.add_metadata('optarg',source[1:-1])
                    elif name in cmdargs.split_list :
                        logger.debug( ' will split items out of \\begin{%r}' % (name,) )
                        t = next(itertokens)
                        while t is not None:
                            if isinstance(t, TokenizerPassThru.Comment):
                                stack.topstream.write('%'+t.source)
                            else:
                                stack.topstream.write(t.source)
                            if isinstance(t, plasTeX.Tokenizer.EscapeSequence):
                                if t.macroName == "item":
                                    _,s = thetex.readArgumentAndSource(spec='[]')
                                    if s:
                                        stack.topstream.write(s)
                                    t = None
                                else:
                                    logger.critical('cannot parse %r inside %r' % (t.source,name) )
                                    t = next(itertokens)
                            else:
                                logger.debug('passing %r inside %r' % (t.source,name) )
                                t = next(itertokens)
                        stack.push(named_stream('E_'+name,parent=stack.topstream))
                    else:
                        logger.debug( ' will not split \\begin{%r}' % (name,) )
                        stack.push('E_'+name)

                elif macroname == "end":
                    name = thetex.readArgument(type=str)
                    if stack.topenv == 'section':
                        if name != 'document':
                            # \sections should not be used inside environments,
                            # this produces weird outline; but just in case..
                            logger.warning(' a \\section was embedded in \\begin{%s}...\\end{%s}' %\
                                           (name,name))
                        pop_section()
                    if in_preamble:
                        logger.info( ' ignore \\end{%r} in preamble' % (name,) )
                    elif (name in cmdargs.split_environment or name in cmdargs.split_list):
                        obj = thedocument.createElement(name)
                        obj.macroMode = Command.MODE_END
                        obj.ownerDocument = thedocument
                        out = obj.invoke(thetex)
                        if out is not None:
                            obj = out
                        pop_section()
                        if stack.topenv != 'E_'+name:
                            log_mismatch(stack.topenv,name)
                            # go on, hope for the best
                        r = stack.pop_stream().writeout()
                        if name == 'document':
                            os_rel_symlink(r,'document.tex', cmdargs.blobs_dir ,
                                           target_is_directory=False, force=True)
                        input_it(r)
                        logger.info( 'did split \\end{%r} into %r' % (name,r) )
                    else:
                        if stack.topenv != 'E_'+name:
                            log_mismatch(stack.topenv,name)
                            # trying to recover
                            stack.pop_str(stopafter = ('E_'+name))
                        else:
                            stack.pop()
                        logger.debug( ' did not split \\end{%r}' % (name,) )
                    #
                    stack.topstream.write(r'\end{%s}' % name)
                elif not in_preamble and macroname in cmdargs.metadata_command :
                    obj = thetex.ownerDocument.createElement(macroname)
                    thetex.currentInput[0].pass_comments = False
                    args = [ thetex.readArgumentAndSource(type=str)[1] for j in range(obj.nargs)]
                    #obj.parse(thetex)
                    thetex.currentInput[0].pass_comments = True
                    logger.info('metadata %r  %r' % (tok,args))
                    j = stack.top
                    a = '' if j == stack.topstream else ('S_'+stack.topenv+'_')
                    for j in args:
                        j =  j.translate({'\n':' '})
                        try:
                            stack.topstream.add_metadata(a+'M_'+macroname,j)
                        except DuplicateLabel:
                            logger.warning('In blob %r file %s line %s ',  stack.topstream.uuid,
                                           thetex.filename, thetex.lineNumber)
                    stack.topstream.write('\\'+macroname+''.join(args))
                    del j,a
                elif macroname == '[':
                    logger.debug(' entering math mode')
                    stack.push('\\[')
                    stack.topstream.write('\\[')
                elif macroname == ']':
                    logger.debug(' exiting math mode')
                    if stack.topenv != '\\[':
                        log_mismatch(stack.topenv,name)
                        # trying to recover
                        stack.pop_str(stopafter = ('\\['))
                    else:
                        stack.pop()
                    stack.topstream.write('\\]')
                elif macroname == 'verb':
                    obj = Base.verb()
                    obj.ownerDocument = thetex.ownerDocument
                    t = obj.invoke(thetex)
                    stack.topstream.write('\\verb')
                    for j in t[1:]:
                        stack.topstream.write(j)
                    del obj,j,t
                elif macroname in ('begingroup','bgroup'):
                    stack.topstream.grouping_depth += 1
                    stack.topstream.write(tok.source)
                elif macroname in ('endgroup','egroup'):
                    if stack.topstream.grouping_depth >= 1:
                        stack.topstream.grouping_depth += -1
                    else:
                        logger.warning('unmatched %r',macroname)
                    stack.topstream.write(tok.source)
                else:
                    #logger.debug(' unprocessed %r', tok.source)
                    stack.topstream.write(tok.source)
            elif isinstance(tok, plasTeX.Tokenizer.BeginGroup):
                stack.topstream.grouping_depth += 1
                stack.topstream.write(tok.source)
            elif isinstance(tok, plasTeX.Tokenizer.EndGroup):
                if stack.topstream.grouping_depth >= 1:
                    stack.topstream.grouping_depth += -1
                else:
                    logger.warning('unmatched EndGroup token')
                stack.topstream.write(str(tok))
            else:
                stack.topstream.write(str(tok))
        pop_paragraph()
        pop_section()
        # main
        M = stack.pop(checknonempty=False)
        if isinstance(M,named_stream) and M.environ == 'main_file':
            r = M.writeout()
        else:
            logger.error('disaligned stack, topmost blob is not the main_file: %r' % (M,))
    except:
        raise
    finally:
        if disaster_recovery:
            while stack:
                M = stack.pop()
                logger.critical('writing orphan output %r',M)
                if isinstance(M,named_stream):
                    M.writeout()


def add_arguments_to_parser(parser):
    parser.add_argument('input_file', help='the input TeX or LaTeX file')
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--split-sections','--SS',action='store_true',help='split each section in a separate blob')
    parser.add_argument('--split-environment','--SE',action='append',
                        help='split the content of this LaTeX environment in a separate blob',
                        default=['document'])
    parser.add_argument('--private-environment',action='append',default=[],
                        help='split this environment and mark as access=private')
    parser.add_argument('--split-list','--SL',action='append',help='split each \\item of this environment in a separate blob', default=[])
    parser.add_argument('--split-paragraph',type=int,help='split paragraphs in separate blob when longer than N')
    parser.add_argument('--split-all-theorems','--SAT',action='store_true',help='split any theorem defined by \\newtheorem in a separate blob, as if each theorem was specified by --split-environment ')
    parser.add_argument('--metadata-command','--MC',action='append',
                        help='store the argument of this TeX command as metadata for the blob (some defaults are provided)',
                        default = default_metadata )
    parser.add_argument('--split-graphic','--SG',action='append',
                        default=['includegraphics'],
                        help='copy graphics for this command, as blobs')
    parser.add_argument('--zip-sections','--ZS',action='store_true',
                        help='omit intermediate blob for \\include{} of a single section; implies --SS')
    parser.add_argument('--verbatim_environment','--VE',action='append',help='verbatim environment, whose content will not be parsed', default=['verbatim','Filesave'])
    parser.add_argument('--symlink-input','--SI',action='store_true',help='create a symlink for each file that is parsed (by `\\input` or `\\include` or `\\includegraphics`)')
    parser.add_argument('--add-UUID','--AU', type=str,choices={"yes","y", "no","n","auto","a"},
                        default={True:'yes',False:"no","auto":"auto"}[ColDoc_write_UUID],
                        help="add \\uuid{UUID} commands, can be `yes` `no` or `auto`")
    parser.add_argument('--latex-engine',type=str,choices=[a[0] for a in ColDoc_latex_engines],
                        help="LaTeX engine used to compile this document",
                        default='pdflatex')
    parser.add_argument('--author',action='append',default=[],
                        help='add as author of this LaTeX')
    parser.add_argument('--EDB',action='store_true',help='add EDB metadata, lists and environments')
    #https://stackoverflow.com/a/31347222/5058564
    stripgroup = parser.add_mutually_exclusive_group()
    stripgroup.add_argument('--strip',action='store_true',default=ColDoc_blob_rstrip,\
                            help='strips the last lines in blobs if they are all made of whitespace')
    stripgroup.add_argument('--no-strip',action='store_false',dest='strip',\
                            help='do not --strip')
    #
    SPgroup = parser.add_mutually_exclusive_group()
    SPgroup.add_argument('--split-preamble','--SP',action='store_true',
                         default=True, help='split the preamble in a separate blob')
    SPgroup.add_argument('--dont-split-preamble','--noSP',action='store_false',
                         dest='split_preamble',help='do not --split-preamble. (Warning this is not well supported)')
    #
    parser.set_defaults(strip=ColDoc_blob_rstrip)


def main(args, metadata_class, coldoc = None):
    " `coldoc` is the nickname of the ColDoc , or the Django class for it"
    # normalize
    if args.zip_sections: args.split_sections = True
    args.add_UUID = {"yes":True,"y":True,"no":False,"n":False,"a":"auto","auto":"auto"}[args.add_UUID]
    #
    named_stream._default_rstrip = args.strip
    named_stream._default_write_UUID = args.add_UUID
    #
    args.split_environment += args.private_environment
    #
    verbose = args.verbose
    assert type(verbose) == int and verbose >= 0
    if verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    #
    if not os.path.exists(args.blobs_dir):
        os.mkdir(args.blobs_dir)
    assert os.path.isdir(args.blobs_dir), ' not a dir %r' % args.blobs_dir
    assert os.path.isfile(args.input_file)

    mytex = TeX()
    mydocument = mytex.ownerDocument
    mycontext = mydocument.context
    if args.split_sections:
        mycontext.newcommand('section',1,r'\section{#1}')
        mycontext.newcommand('subsection',1,r'\subsection{#1}')

    for name in args.metadata_command :
        d =  '\\' + name + '{#1}'
        #mycontext.newcommand(name, n, d)
        n = 1
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':n, 'opt':None, 'definition':d})
        assert newclass.nargs == n
        mycontext.addGlobal(name, newclass)

    if args.EDB:
        #
        thecounter = 'thmCount'
        mycontext.newcounter(thecounter, initial=0) #, resetby=parent)
        for name in 'wipExercise','extrastuff','delasol':
            data = {
                    'macroName': name,
                    'counter': thecounter,
                    'thehead': name,
                    'thename': name,
                    'labelable': True,
                    'forcePars': True,
                    'thestyle': 'plain'
                }
            th = type(name, (amsthm.theoremCommand,), data)
            mycontext.addGlobal(name, th)
            args.split_environment.append(name)

    for j in 'UUID', 'SEC', 'tmp':
        d = osjoin(args.blobs_dir,j)
        if not os.path.isdir(d):
            os.mkdir(d)
    # save cmdline args
    args.cwd = os.getcwd()
    f = osjoin(args.blobs_dir, '.blob_inator-args.json')
    if os.path.exists(f):
        sys.stderr.write("Cannot reuse this same directory: %r\n"%(f,))
        return 1
    with open(f, 'w') as a:
        json.dump(args.__dict__, a, indent=2)
    #
    logger.info("processing %r" % args.input_file)
    try:
        blob_inator(mytex, mydocument, mycontext, args, metadata_class, coldoc)
    except:
        logger.exception('blob_inator killed by exception:')
        return 1
    else:
        logger.info("end of file")
    # save again, with all theorems found with the option --SAT
    f = osjoin(args.blobs_dir, '.blob_inator-args.json')
    with open(f, 'w') as a:
        json.dump(args.__dict__, a, indent=2)
    return 0

def parse_EDB(args):
    if args.EDB :
        args.split_list += ['Exercises',]
        #
        args.metadata_command += [ 'keywords', 'prerequisites',  'difficulty', 'notes', 'olduuid',
                                   'indexLit', 'indexLen', 'proposto', 'previsto', 'svolto']
        args.split_graphic += ['margpic','adjincludegraphics']
        args.private_environment += ['delasol','extrastuff','wipver','wipExercise']
        args.latex_engine = 'xelatex'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Splits a TeX or LaTeX input into blobs',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--blobs-dir',type=str,default=ColDoc_as_blobs,\
                        help='directory where to save the blob_ized output',\
                        required=(ColDoc_as_blobs is None))
    parser.add_argument('--coldoc-nick',type=str,\
                        help='nickname for the new coldoc document') # not required
    add_arguments_to_parser(parser)
    args = parser.parse_args()
    parse_EDB(args)
    sys.exit(main(args, FMetadata, coldoc = args.coldoc_nick))
