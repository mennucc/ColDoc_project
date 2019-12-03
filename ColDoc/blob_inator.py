#!/usr/bin/python3

""" the Blob Inator
splits the input into blobs
"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil, re, json
import os.path
from os.path import join as osjoin

import ColDocLogging

import logging
logger = logging.getLogger(__name__)


a = os.path.realpath(sys.argv[0])
a = os.path.dirname(a)
a = os.path.dirname(a)
assert os.path.isdir(a), a
a = osjoin(a,'lib')
assert os.path.isdir(a), a
sys.path.insert(0, a)
del a


############## ColDoc stuff

from config import *

from utils import *



#########################################################################
import TokenizerPassThru

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
      the file will be written in a new UUID under `basepath` ; but see `self.filename`
      and `self.metadata_filename`
    """
    #
    _re_spaces_ =  re.compile('^[ \t\n]+$')
    _default_rstrip = ColDoc_blob_rstrip
    #
    def __init__(self, basepath, environ ,
                lang = ColDoc_lang, extension = '.tex',
                early_UUID = ColDoc_early_UUID,
                parentUUID = None, parent = None,
                *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store parameters
        assert os.path.isdir(basepath)
        self._basepath = basepath
        self._environ = environ
        self._extension = extension
        self._lang = lang
        # prepare internal stuff
        self._was_written = False
        self._uuid = None
        self._filename = None
        self._metadata_filename = None
        self._dir = None
        self._symlink_dir = None
        self._symlink_files = set()
        # save from gc, for __del__ method
        self._sys = sys
        self._open = open
        self._logger = logger
        # set up UUID
        if early_UUID:
            self._find_unused_UUID()
        # prepare metadata
        self._metadata = Metadata()
        self.add_metadata('environ', environ)
        self.add_metadata('extension', extension)
        self.add_metadata('lang', lang)
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
    def __repr__(self):
        return ('<named_stream(basepath=%r, environ=%r, lang=%r, extension = %r, uuid=%r)>' % \
               (self._basepath,self._environ,self._lang,self._extension,self._uuid))
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
        self._metadata_filename = osjoin(d, 'metadata')
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
        self._metadata_filename = filename + '~metadata'
    @property
    def metadata_filename(self):
        "the filename relative to `basepath` where the metadata will be saved"
        return self._metadata_filename
    def __len__(self):
        return len(self.getvalue())
    def add_metadata(self,T,E, braces=False):
        """ The parameter `braces` dictates if `E` will be enclosed in {};
        `braces` may be `True`,`False` or `None` (which means 'autodetect')
        """
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
    _comment_out_uuid_in = ColDoc_comment_out_uuid_in
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
    def writeout(self, write_UUID = ColDoc_write_UUID, rstrip = None):
        """Writes the content of the file; returns the `filename` where the content was stored,
        relative to `basedir` (using the `symlink_dir` if provided).
        
        - If `write_UUID` is `True`, the UUID will be written at the beginning of the blob.
        
        - If `write_UUID` is 'auto', the UUID will be written,
          but it will be commented out in 'document', 'main_file', 'preamble', 'section' blobs.
          (It is anyway added after each '\section' command).
        
        - If `write_UUID` is `False`, no UUID will be written.
        
        - If `rstrip` is `True`, will use `self.rstrip` to strip away final lines of only whitespace
        """
        if rstrip is None : rstrip = self._default_rstrip
        #
        cmt = ''
        assert write_UUID in (True,False,'auto')
        if write_UUID == 'auto' and self.environ in self._comment_out_uuid_in:
            cmt = '%%'
            write_UUID = True
        if self._filename is None:
            self._find_unused_UUID()
        if self._was_written :
            logger.critical('file %r was already written ' % self._filename)
            return self._filename
        if self.closed :
            logger.error('file %r was closed before writeout' % self._filename)
        filename = osjoin(self._basepath, self._filename)
        metadata_file = osjoin(self._basepath, self._metadata_filename)
        if True: #len(self.getvalue()) > 0:
            self.flush()
            logger.info("writeout file %r metadata %r " % (self._filename, self._metadata_filename))
            z = self._open(filename ,'w')
            if write_UUID and self.uuid:
                z.write("%s\\uuid{%s}%%\n" % (cmt,self.uuid,))
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
            self._metadata.write(metadata_file)
            r =  self._filename
            # no more messing with this class
            self._was_written = True
            self.close()
            if self._symlink_dir:
                os_rel_symlink(self._dir,self._symlink_dir,basedir=self._basepath,
                               target_is_directory=True)
                r = osjoin(self._symlink_dir, os.path.basename(filename))
            if self._symlink_files:
                for j in self._symlink_files:
                    os_rel_symlink(r, j ,basedir=self._basepath,
                                   target_is_directory=False)
            return r
    def __del__(self):
        if not self._was_written :
            self._logger.critical('this file was not written %r' % self._filename)

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

class EnvStreamStack(object):
    """ a class that manages a stack of named_stream and LaTeX environments,
    interspersed"""
    def __init__(self):
        self._stack=[]
        self._topstream = None
    def __len__(self):
        return len(self._stack)
    @property
    def top(self):
        " the top element"
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
    def _set_topstream(self):
        self._topstream = None
        for j in reversed(self._stack):
            if isinstance(j,named_stream):
                self._topstream = j
                break
    def push(self,o):
        assert isinstance(o, (str,named_stream))
        self._stack.append(o)
        if isinstance(o,named_stream):
            self._topstream = o
    def pop(self, add_as_child = True):
        """ pops topmost element ;
        if `add_as_child` and topmost element was a stream,
        write its UUID and filename in metadata of the parent stream"""
        o = self._stack.pop()
        if isinstance(o, named_stream):
            self._set_topstream()
            if add_as_child and self._topstream is not None \
               and isinstance(self._topstream,named_stream):
                if o.uuid:
                    self._topstream.add_metadata('child_uuid',o.uuid)
                #if o.filename:
                #    self._topstream.add_metadata('child_filename',o.filename)
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
    def pop_stream(self):
        " pops the topmost stream, w/o touching the non-stream elements of the stack"
        t = None
        for n,j in enumerate(self._stack):
            if isinstance(j,named_stream):
                t=n
        assert t is not None
        O = self._stack[t]
        del self._stack[t]
        self._set_topstream()
        return O

def blob_inator(thetex, thedocument, thecontext, cmdargs):
    use_plastex_parse = True
    blobs_dir=cmdargs.blobs_dir
    shift_eol=True
    # normalize input file path
    input_file = os.path.abspath(cmdargs.input_file)
    input_basedir = os.path.dirname(input_file)
    #
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    in_preamble = False
    # map to avoid duplicating the same input on two different blobs;
    # each key is converted to an absolute path relative to `blobs_dir`;
    # the value is either the `named_stream` or a path relative to `blobs_dir`
    file_blob_map = absdict(basedir = input_basedir, loggingname='file_blob_map')
    #
    n = 0
    thetex.input(open(cmdargs.input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    stack = EnvStreamStack()
    output = named_stream(blobs_dir,'main_file')
    output.add_metadata('original_filename',input_file)
    file_blob_map[input_file] = output
    output.symlink_file_add('main.tex')
    if cmdargs.symlink_input:
        output.symlink_file_add(os.path.basename( input_file))
    stack.push(output)
    del output, input_file
    def pop_section():
        # do not destroy stack, stack.pop_str()
        if stack.topstream.environ == 'section':
            r = stack.pop_stream().writeout()
            stack.topstream.write(r'\input{%s}' % r)
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
    #
    itertokens = thetex.itertokens()
    try:
        for tok in itertokens:
            n += len(tok.source)
            if isinstance(tok, plasTeX.Tokenizer.Comment):
                a = tok.source
                if hasattr(plasTeX.Tokenizer.Comment,'source'):
                    # my patch adds 'source' to Comment, so that '%' is already prepended
                    assert a[0] == '%'
                    stack.topstream.write(a)
                else:
                    stack.topstream.write('%'+a)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                if tok.macroName == 'documentclass':
                    in_preamble = True
                    obj = Base.documentclass()
                    a = obj.parse(thetex)
                    # implement obj.load(thetex, a['name'], a['options'])
                    thecontext.loadPackage(thetex, a['name']+'.cls',
                                           a['options'])
                    stack.topstream.write(obj.source)
                    if cmdargs.split_preamble:
                        stack.push(named_stream(blobs_dir,'preamble', parent=stack.topstream))
                elif cmdargs.split_sections and tok.macroName == 'section':
                    pop_section()
                    #obj = Base.section()
                    #obj.parse(thetex)
                    # the above fails, we are not providing the full context to it
                    # so we imitate it, iterating over obj.arguments:
                    argSource = ''
                    for spec in '*','[]',None: 
                        output, source = thetex.readArgumentAndSource(spec=spec) #parentNode=obj,                                                                   name=arg.name,                                                                   **arg.options)
                        #logger.debug(' spec %r output %r source %r ' % (spec,output,source) )
                        argSource += source
                    name = source[1:-1]
                    n = new_section_nr(blobs_dir = blobs_dir)
                    u = int_to_uuid(n)
                    f = 'SEC/%s_%s' % (u , slugify(name) )
                    logger.info('starting section %r . linked by dir %r' % (name,f))
                    add_child = True
                    if cmdargs.zip_sections:
                        if stack.topstream != stack.top:
                            logger.warning("cannot zip section %r , inside an environment" % (name,))
                        elif stack.topenv == 'section':
                            logger.warning("cannot zip the section %, it is after a previous section in blob %r" %\
                                           (name,stack.topstream))
                        elif len(stack.topstream) > 0:
                            logger.warning("cannot zip section %r , parent blob %r has length %d (try to remove cruft before \\section)" %\
                                           (name,stack.topstream,len(stack.topstream)))
                        else:
                            add_child = False
                    if add_child:
                        stack.push(named_stream(blobs_dir,'section', parent=stack.topstream))
                    stack.topstream.symlink_dir = f
                    stack.topstream.add_metadata('section',argSource, braces=False)
                    stack.topstream.write('\\section'+argSource)
                    if stack.topstream.uuid and ColDoc_write_UUID:
                        stack.topstream.write("\\uuid{%s}" % (stack.topstream.uuid,))
                elif cmdargs.split_all_theorems and tok.macroName == 'newtheorem':
                    obj = amsthm.newtheorem()
                    obj.parse(thetex)
                    stack.topstream.write(obj.source)
                    logger.info('adding to splited environments: %r' % obj.source)
                    th = new_theorem(obj.attributes, thedocument, thecontext)
                    name = obj.attributes['name']
                    cmdargs.split_environment.append(name)
                    thecontext.addGlobal(name, th)
                    del th
                elif tok.macroName in ("input","include"):
                    if tok.macroName == "include" and stack.topstream.environ == "section":
                        r = stack.pop_stream().writeout()
                        stack.topstream.write('\\input{%s}' % (r,))
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                        # only follow local files
                        #inputfile = thetex.kpsewhich(inputfile)
                    else:
                        inputfile = thetex.readArgument(type=str)
                    if inputfile in file_blob_map:
                        O = file_blob_map[inputfile]
                        if not isinstance(O,named_stream):
                            logger.error("the input %r was already parsed as object %r ?!?",
                                         inputfile,O)
                        elif not O.closed:
                            logger.critical("recursive input: %r as %r", inputfile, O)
                            raise RuntimeError("recursive input: %r as %r" % (inputfile, O))
                        logger.info("duplicate input, parsed once: %r", inputfile)
                        stack.topstream.write('\\%s{%s}' % (tok.macroName,O.filename))
                    else:
                        newoutput = named_stream(blobs_dir,tok.macroName,parent=stack.topstream)
                        newoutput.add_metadata(r'original_filename',inputfile)
                        stack.push(newoutput)
                        if cmdargs.symlink_input:
                            newoutput.symlink_file_add( inputfile + ('' if inputfile[-4:] == '.tex' else '.tex'))
                        if not os.path.isabs(inputfile):
                            inputfile = os.path.join(input_basedir,inputfile)
                        if not os.path.isfile(inputfile):
                            inputfile += '.tex'
                        assert os.path.isfile(inputfile)
                        file_blob_map[inputfile] = newoutput
                        del newoutput
                        logger.info(' processing %r ' % (inputfile))
                        a=io.StringIO()
                        a.write('\\'+specialblobinatorEOFcommand)
                        a.seek(0)
                        a.name='specialblobinatorEOFcommand'
                        thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
                        del a
                        thetex.input(open(inputfile), Tokenizer=TokenizerPassThru.TokenizerPassThru)
                    del inputfile
                elif tok.macroName == specialblobinatorEOFcommand:
                    pop_section()
                    # pops the output when it ends
                    z = stack.pop()
                    r = z.writeout()
                    logger.info('end input, writing %r',r)
                    a=z.environ
                    if a == 'include' and r[-4:] == '.tex':
                        r=r[:-4]
                    stack.topstream.write('\\%s{%s}' % (a,r))
                    assert a in ('input','include')
                    del r,z,a
                elif not in_preamble and cmdargs.copy_graphicx \
                     and tok.macroName == "includegraphics":
                    if use_plastex_parse:
                        obj = graphicx.includegraphics()
                        a = obj.parse(thetex)
                        inputfile = a['file']
                        a = obj.source
                        j = a.index('{')
                        cmd = a[:j]
                        del a, obj
                    else:
                        cmd = '\\includegraphics'
                        for spec in '*','[]',None: 
                            output, source = thetex.readArgumentAndSource(spec=spec)
                            if spec:
                                cmd += source
                            else:
                                inputfile = source[1:-1]
                    assert isinstance(inputfile,str)
                    logger.debug('parsing %r' , cmd+'{'+inputfile+'}')
                    assert not os.path.isabs(inputfile), "absolute path not supported: "+cmd+'{'+inputfile+'}'
                    if inputfile in file_blob_map:
                        O = file_blob_map[inputfile]
                        if not isinstance(O,str):
                            logger.critical("the input %r was already parsed as object %r",
                                            inputfile,O)
                            raise RuntimeError("the input %r was already parsed as object %r" %
                                               (inputfile,O))
                        logger.info("duplicate graphical input, copied once: %r", inputfile)
                        stack.topstream.write(cmd+'{'+file_blob_map[inputfile]+'}')
                    else:
                        di,bi = os.path.split(inputfile)
                        bi,ei=os.path.splitext(bi)
                        assert inputfile == osjoin(di,bi+ei)
                        if ei and not os.path.isfile(osjoin(input_basedir,inputfile)):
                            logger.error(' while parsing %r, no  such file: %r' %\
                                (cmd+'{'+inputfile+'}',fi,))
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
                        fm = Metadata()
                        fm['uuid'] = uuid
                        fm['original_filename'] = inputfile
                        fm['original_command'] = cmd
                        fm['parent_uuid'] = stack.topstream.uuid
                        del uuid
                        # will load the same extension, if specified
                        stack.topstream.write(cmd+'{'+fo+ei+'}')
                        #
                        file_blob_map[inputfile] = fo+ei
                        file_blob_map[osjoin(di,bi)] = fo
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
                            file_blob_map[fii] = fo+ext
                            #
                        fm.write(osjoin(blobs_dir,do,"metadata"))
                        del do,fo,fm,exts,cmd,di,bi,ei,ext,fii
                elif tok.macroName == "item":
                    e = stack.topenv
                    if len(e) >= 3 and e[:2] == 'E_' and e[2:] in cmdargs.split_list :
                        r = stack.pop().writeout()
                        logger.info('end item, writing %r',r)
                        stack.topstream.write('\\input{%s}%%\n\\item' % (r,))
                        _,source = thetex.readArgumentAndSource('[]')
                        if source: 
                            stack.topstream.write(source)
                        stack.push(named_stream(blobs_dir,e,parent=stack.topstream))
                        del r
                    else:
                        stack.topstream.write('\\item')
                    del e
                elif tok.macroName == "begin":
                    name = mytex.readArgument(type=str)
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
                            stack.topstream.write('\\input{%s}%%\n' % r)
                        in_preamble = False
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
                        if isinstance(obj, amsthm.theoremCommand):
                            _,source = thetex.readArgumentAndSource('[]')
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
                        stack.push(named_stream(blobs_dir,'E_'+name,parent=stack.topstream))
                        if source:
                            assert source[0] == '[' and source[-1] == ']'
                            stack.topstream.add_metadata('optarg',source[1:-1])
                    elif name in cmdargs.split_list :
                        logger.debug( ' will split items out of \\begin{%r}' % (name,) )
                        t = next(itertokens)
                        while t is not None:
                            if isinstance(t, plasTeX.Tokenizer.Comment):
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
                        stack.push(named_stream(blobs_dir,'E_'+name,parent=stack.topstream))
                    else:
                        logger.debug( ' will not split \\begin{%r}' % (name,) )
                        stack.push('E_'+name) 

                elif tok.macroName == "end":
                    name = thetex.readArgument(type=str)
                    if not in_preamble and stack.topenv == 'section' and name != 'document':
                        # \sections should not be used inside environments,
                        # this produces weird outline; but just in case..
                        logger.warning(' a \\section was embedded in \\begin{%s}...\\end{%s}' %\
                                       (name,name))
                        r = stack.pop().writeout()
                        stack.topstream.write(r'\input{%s}' % (r,) )
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
                        stack.topstream.write('\\input{%s}%%\n' % r)
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
                elif not in_preamble and tok.macroName in cmdargs.metadata_command :
                    obj = thetex.ownerDocument.createElement(tok.macroName)
                    args = [ thetex.readArgumentAndSource(type=str)[1] for j in range(obj.nargs)]
                    #obj.parse(thetex)
                    logger.info('metadata %r  %r' % (tok,args))
                    j = stack.top
                    a = '' if j == stack.topstream else ('S_'+stack.topenv+'_')
                    for j in args:
                        j =  j.translate({'\n':' '})
                        stack.topstream.add_metadata(a+'M_'+tok.macroName,j)
                    stack.topstream.write('\\'+tok.macroName+''.join(args))
                    del j,a
                elif tok.macroName == '[':
                    logger.debug(' entering math mode')
                    stack.push('\\[')
                    stack.topstream.write('\\[')
                elif tok.macroName == ']':
                    logger.debug(' exiting math mode')
                    if stack.topenv != '\\[':
                        log_mismatch(stack.topenv,name)
                        # trying to recover
                        stack.pop_str(stopafter = ('\\['))
                    else:
                        stack.pop()
                    stack.topstream.write('\\]')
                else:
                    #logger.debug(' unprocessed %r', tok.source)
                    stack.topstream.write(tok.source)
            else:
                stack.topstream.write(str(tok))
        pop_section()
        # main
        M = stack.pop()
        if isinstance(M,named_stream) and M.environ == 'main_file':
            r = M.writeout()
        else:
            logger.error('disaligned stack, topmost blob is not the main_file: %r' % (M,))
    except:
        raise
    finally:
        while stack:
            M = stack.pop()
            logger.critical('writing orphan output %r',M)
            if isinstance(M,named_stream):
                M.writeout()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Splits a TeX or LaTeX input into blobs',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input_file', help='the input TeX or LaTeX file')
    parser.add_argument('--blobs-dir',type=str,default=ColDoc_as_blobs,\
                        help='directory where to save the blob_ized output',\
                        required=(ColDoc_as_blobs is None))
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--split-sections','--SS',action='store_true',help='split each section in a separate blob')
    parser.add_argument('--split-environment','--SE',action='append',help='split the content of this LaTeX environment in a separate blob', default=[])
    parser.add_argument('--split-list','--SL',action='append',help='split each \\item of this environment in a separate blob', default=[])
    parser.add_argument('--split-preamble','--SP',action='store_true',help='split the preamble a separate blob')
    parser.add_argument('--split-all-theorems','--SAT',action='store_true',help='split any theorem defined by \\newtheorem in a separate blob, as if each theorem was specified by --split-environment ')
    parser.add_argument('--metadata-command','--MC',action='append',
                        help='store the argument of this TeX command as metadata for the blob (\\label, \\uuid are always metadata)',
                        default = [ 'label', 'uuid', 'index' ] )
    parser.add_argument('--copy-graphicx','--CG',action='store_true',help='copy graphicx as blobs')
    parser.add_argument('--zip-sections','--ZS',action='store_true',help='omit intermediate blob for \\include{} of a single section')
    parser.add_argument('--verbatim_environment','--VE',action='append',help='verbatim environment, whose content will not be parsed', default=['verbatim','Filesave'])
    parser.add_argument('--symlink-input','--SI',action='store_true',help='create a symlink for each file that is parsed (by `\\input` or `\\include` or `\\includegraphics`)')
    parser.add_argument('--EDB',action='store_true',help='add EDB metadata, lists and environments')
    #https://stackoverflow.com/a/31347222/5058564
    stripgroup = parser.add_mutually_exclusive_group()
    stripgroup.add_argument('--strip',action='store_true',default=ColDoc_blob_rstrip,\
                            help='strips the last lines in blobs if they are all made of whitespace')
    stripgroup.add_argument('--no-strip',action='store_false',dest='strip',\
                            help='do not --strip')
    parser.set_defaults(strip=ColDoc_blob_rstrip)
    #
    args = parser.parse_args()
    #
    named_stream._default_rstrip = args.strip
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
    assert os.path.isdir(args.blobs_dir), ' not a dir %r' % args.blobs_dir
    assert os.path.isfile(args.input_file)

    mytex = TeX()
    mydocument = mytex.ownerDocument
    mycontext = mydocument.context
    if args.split_sections:
        mycontext.newcommand('section',1,r'\section{#1}')
        mycontext.newcommand('subsection',1,r'\subsection{#1}')

    if args.EDB :
        args.metadata_command += [ 'keywords', 'prerequisites',  'difficulty','indexLit', 'indexLen']
    for name in args.metadata_command :
        d =  '\\' + name + '{#1}'
        #mycontext.newcommand(name, n, d)
        n = 1
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':n, 'opt':None, 'definition':d})
        assert newclass.nargs == n
        mycontext.addGlobal(name, newclass)

    if args.EDB:
        for name in 'Exercises',:
            # fixme should create list type environment in mycontext
            args.split_list.append(name)
        #
        args.split_environment.append('document')
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

    for j in 'UUID', 'SEC':
        d = osjoin(args.blobs_dir,j)
        if not os.path.isdir(d):
            os.mkdir(d)
    # save cmdline args
    args.cwd = os.getcwd()
    with open(osjoin(args.blobs_dir, '.blob_inator-args.json'), 'w') as a:
        json.dump(args.__dict__, a, indent=2)
    #
    logger.info("processing %r" % args.input_file)
    blob_inator(mytex, mydocument, mycontext, args)
    logger.info("end of file")


