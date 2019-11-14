#!/usr/bin/python3

""" the Blob Inator
splits the input into blobs
"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil
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
    def __init__(self, basepath, environ ,
                lang = ColDoc_lang, extension = '.tex',
                early_UUID = ColDoc_early_UUID,
                parentFile = None, parentUUID = None, parent = None,
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
        # save from gc, for __del__ method
        self._sys = sys
        self._open = open
        self._logger = logger
        # set up UUID
        if early_UUID:
            self._find_unused_UUID()
        # prepare metadata
        self._metadata_txt = '\\environ{%s}\n\\extension{%s}\n\\lang{%s}\n' % ( environ, extension, lang )
        if parent is not None:
            if parentFile is None : parentFile = parent.filename
            if parentUUID is None : parentUUID = parent.uuid
        if parentFile:
            self.add_metadata(r'\parentFile', parentFile)
        if parentUUID:
            self.add_metadata(r'\parentUUID', parentUUID)
        elif environ != 'MainFile':
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
    def add_metadata(self,T,E, braces=None):
        """ The parameter `braces` dictates if `E` will be enclosed in {};
        `braces` may be `True`,`False` or `None` (which means 'autodetect')
        """
        assert isinstance(E,str)
        assert E
        assert braces in (True,False,None)
        E = E.translate({10:32})
        if braces is False or \
           ( E[0] == '{' and E[-1] == '}' and braces is None ):
            self._metadata_txt += '%s%s\n' %(  T,E)
        else:
            self._metadata_txt += '%s{%s}\n' %(  T,E)
    #
    _comment_out_uuid_in = ('document','MainFile','Preamble','section')
    #
    def writeout(self, write_UUID = ColDoc_write_UUID):
        """Writes the content of the file; returns the `filename` where the content was stored,
        relative to `basedir` (using the `symlink_dir` if provided).
        
        - If `write_UUID` is `True`, the UUID will be written at the beginning of the blob.
        
        - If `write_UUID` is 'auto', the UUID will be written,
          but it will be commented out in 'document', 'MainFile', 'Preamble', 'section' blobs.
          (It is anyway added after each '\section' command).
        
        - If `write_UUID` is `False`, no UUID will be written.
        """
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
        filename = osjoin(self._basepath, self._filename)
        metadata_file = osjoin(self._basepath, self._metadata_filename)
        if True: #len(self.getvalue()) > 0:
            self.flush()
            logger.info("writeout file %r metadata %r " % (self._filename, self._metadata_filename))
            z = self._open(filename ,'w')
            if write_UUID and self.uuid:
                z.write("%s\\uuid{%s}%%\n" % (cmt,self.uuid,))
            z.write(self.getvalue())
            z.close()
            self._open(metadata_file,'w').write(self._metadata_txt)
            r =  self._filename
            # no more messing with this class
            self._was_written = True
            self.close()
            if self._symlink_dir:
                os_rel_symlink(self._dir,self._symlink_dir,basedir=self._basepath,
                               target_is_directory=True)
                r = osjoin(self._symlink_dir, os.path.basename(filename))
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
                    self._topstream.add_metadata('\\childUUID',o.uuid)
                if o.filename:
                    self._topstream.add_metadata('\\childFilename',o.filename)
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

def blob_inator(input_file, thetex, thedocument, thecontext, cmdargs):
    use_plastex_parse = True
    blobs_dir=cmdargs.blobs_dir
    shift_eol=True
    input_basedir = os.path.dirname(cmdargs.input_file)
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    in_preamble = False
    n = 0
    thetex.input(open(input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    stack = EnvStreamStack()
    output = named_stream(blobs_dir,'MainFile')
    output.add_metadata(r'\originalFileName',input_file)
    stack.push(output)
    del output
    def pop_section():
        stack.pop_str()
        if stack.topenv == 'section':
            r = stack.pop().writeout()
            stack.topstream.write(r'\input{%s}' % r)
        stack.pop_str()
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
                stack.topstream.write('%'+tok.source)
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
                        stack.push(named_stream(blobs_dir,'Preamble', parent=stack.topstream))
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
                    stack.push(named_stream(blobs_dir,'section', parent=stack.topstream))
                    stack.topstream.symlink_dir = f
                    stack.topstream.add_metadata('\\section',argSource, braces=False)
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
                    if tok.macroName == "include" and stack.topenv == "section":
                        r = stack.pop().writeout()
                        stack.topstream.write('\\input{%s}' % (r,))
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                        # only follow local files
                        #inputfile = thetex.kpsewhich(inputfile)
                    else:
                        inputfile = thetex.readArgument(type=str)
                    newoutput = named_stream(blobs_dir,tok.macroName,parent=stack.topstream)
                    newoutput.add_metadata(r'\originalFileName',inputfile)
                    stack.push(newoutput)
                    del newoutput
                    if not os.path.isabs(inputfile):
                        inputfile = os.path.join(input_basedir,inputfile)
                    if not os.path.isfile(inputfile):
                        inputfile += '.tex'
                    assert os.path.isfile(inputfile)
                    logger.info(' processing %r ' % (inputfile))
                    a=io.StringIO()
                    a.write('\\'+specialblobinatorEOFcommand+'\n')
                    a.seek(0)
                    a.name='specialblobinatorEOFcommand'
                    thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
                    del a
                    thetex.input(open(inputfile), Tokenizer=TokenizerPassThru.TokenizerPassThru)
                elif tok.macroName == specialblobinatorEOFcommand:
                    pop_section()
                    # pops the output when it ends
                    z = stack.pop()
                    r = z.writeout()
                    logger.info('end input, writing %r',r)
                    a=z.environ
                    if a == 'include' and r[-4:] == '.tex':
                        r=r[:-4]
                    stack.topstream.write('\\%s{%s}%%\n' % (a,r))
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
                    assert not os.path.isabs(inputfile), "absolute path not supported: "+cmd+'{'+inputfile+'}'
                    fi=osjoin(input_basedir,inputfile)
                    di=os.path.dirname(fi)
                    bi=os.path.basename(fi)
                    bi,ei=os.path.splitext(bi)
                    assert fi == osjoin(di,bi+ei)
                    if ei and not os.path.isfile(fi):
                        logger.error(' while parsing %r, no  such file: %r' %\
                            (cmd+'{'+inputfile+'}',fi,))
                    # find all interesting files
                    is_graph = False
                    exts = []
                    for j in os.listdir(di):
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
                    fm = open(osjoin(blobs_dir,do,"metadata"),'w')
                    fm.write('\\uuid{%s}\n\\originalFileName{%s}\n' % (uuid,inputfile,))
                    del uuid
                    # will load the same extension, if specified
                    stack.topstream.write(cmd+'{'+fo+ei+'}')
                    # copy all files with same base, different extensions
                    ext = fii = None
                    for ext in exts:
                        fii = osjoin(di,bi+ext)
                        logger.info(' copying %r to %r' % (fii,fo+ext) )
                        shutil.copy(fii,osjoin(blobs_dir,fo+ext))
                        fm.write('\\extension{%s}\n' % (ext,))
                    fm.close()
                    del do,fo,fm,exts,cmd,fi,di,bi,ei,ext,fii
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
                            assert old.environ == 'Preamble', " in preamble, the element %r does not match" % old
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
                            stack.topstream.add_metadata('\\optarg',source[1:-1])
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
                            continue
                        r = stack.pop().writeout()
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
                elif not in_preamble and \
                     tok.macroName in cmdargs.metadata_command :
                    obj = thetex.ownerDocument.createElement(tok.macroName)
                    args = [ thetex.readArgumentAndSource(type=str)[1] for j in range(obj.nargs)]
                    #obj.parse(thetex)
                    logger.info('metadata %r  %r' % (tok,args))
                    for j in args:
                        j =  j.translate({'\n':' '})
                        stack.topstream.add_metadata('\\'+tok.macroName,j)
                    stack.topstream.write(obj.source+''.join(args))
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
        if M.environ == 'MainFile':
            r = M.writeout()
            os_rel_symlink(r, 'main.tex', cmdargs.blobs_dir ,
                           target_is_directory=False, force=True)
        else:
            logger.error('disaligned stack, blob %r is not the MainFile' % (M,))
    except:
        raise
    finally:
        while stack:
            logger.critical('writing orphan output')
            M = stack.pop()
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
    parser.add_argument('--verbatim_environment','--VE',action='append',help='verbatim environment, whose content will not be parsed', default=['verbatim','Filesave'])
    parser.add_argument('--EDB',action='store_true',help='add EDB metadata, lists and environments')
    args = parser.parse_args()
    input_file = args.input_file
    verbose = args.verbose
    assert type(verbose) == int and verbose >= 0
    if verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    #hack
    #input_file = '/home/andrea/Work/CORSI/EDB/EDB.tex'
    assert os.path.isdir(args.blobs_dir), ' not a dir %r' % args.blobs_dir
    assert os.path.isfile(input_file)
    input_basedir = os.path.dirname(input_file)

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

    args.split_environment.append('document')
    if args.EDB:
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


    logger.info("processing %r" % input_file)
    blob_inator(input_file, mytex, mydocument, mycontext, args)
    logger.info("end of file")


