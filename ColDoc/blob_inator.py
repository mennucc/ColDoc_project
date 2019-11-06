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


from base32_crockford import base32_crockford


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
    def __init__(self, basepath, environ , depth,
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
        self._depth = copy.copy(depth)
        # prepare internal stuff
        self._metadata_txt = '\\environ{%s}\n\\extension{%s}\n\\lang{%s}\n' % ( environ, extension, lang )
        if parent:
            if parentFile is None : parentFile = parent.filename
            if parentUUID is None : parentUUID = parent.uuid
        if parentFile:
            self.add_metadata(r'\parentFile', parentFile)
        if parentUUID:
            self.add_metadata(r'\parentUUID', parentUUID)
        self._was_written = False
        #
        self._uuid = None
        self._filename = None
        self._metadata_filename = None
        self._dir = None
        self._symlink_dir = None
        #
        if early_UUID:
            self._find_unused_UUID()
        # save from gc, for __del__ method
        self._sys = sys
        self._open = open
        self._logger = logger

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
    def depth(self):
        return self._depth
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
    def add_metadata(self,T,E):
        assert isinstance(E,str)
        assert E
        E = E.translate({10:32})
        if E[0] == '{':
            self._metadata_txt += '%s%s\n' %(  T,E)
        else:
            self._metadata_txt += '%s{%s}\n' %(  T,E)
    def writeout(self):
        """Writes the content of the file; returns the `filename` where the content was stored,
        relative to `basedir` (using the `symlink_dir` if provided)
        """
        if self._filename is None:
            self._find_unused_UUID()
        assert not self._was_written , 'file %r was already written ' % self._filename
        filename = osjoin(self._basepath, self._filename)
        metadata_file = osjoin(self._basepath, self._metadata_filename)
        if True: #len(self.getvalue()) > 0:
            self.flush()
            logger.info("writeout file %r metadata %r " % (self._filename, self._metadata_filename))
            self._open(filename ,'w').write(self.getvalue())
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
    #property
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
    def pop(self):
        o = self._stack.pop()
        if isinstance(o, named_stream):
            self._set_topstream()
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
    input_basedir = os.path.dirname(cmdargs.input_file)
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    in_preamble = False
    n = 0
    depth = []
    thetex.input(open(input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    output = named_stream(blobs_dir,'MainFile',depth)
    output.add_metadata(r'\originalFileName',input_file)
    out_list = [output]
    del output
    def pops_sections():
        while depth and depth[-1] == 'section':
            r = out_list[-1].writeout()
            out_list.pop()
            out_list[-1].write('\\input{%s}' % r)
            depth.pop()
    #
    itertokens = thetex.itertokens()
    try:
        for tok in itertokens:
            n += len(tok.source)
            if isinstance(tok, plasTeX.Tokenizer.Comment):
                out_list[-1].write('%'+tok.source)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                if tok.macroName == 'documentclass':
                    in_preamble = True
                    obj = Base.documentclass()
                    a = obj.parse(thetex)
                    # implement obj.load(thetex, a['name'], a['options'])
                    thecontext.loadPackage(thetex, a['name']+'.cls',
                                           a['options'])
                    out_list[-1].write(obj.source)
                    if cmdargs.split_preamble:
                        out_list.append(named_stream(blobs_dir,'Preamble',depth, parent=out_list[-1]))
                        depth.append('Preamble')
                elif cmdargs.split_sections and tok.macroName == 'section':
                    pops_sections()
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
                    u = base32_crockford.encode(n)
                    u = u.rjust(3,'0')
                    f = 'SECs/%s_%s' % (u , slugify(name) )
                    logger.info('starting section %r . linked by dir %r' % (name,f))
                    depth.append('section')
                    out_list.append(named_stream(blobs_dir,'section',depth, parent=out_list[-1]))
                    out_list[-1].symlink_dir = f
                    out_list[-1].write('\\section'+argSource)
                    #if len(out_list[-1]) < 30:
                    #    out_list[-1].filename = f
                    #    out_list[-1].add_metadata('\\section',name)
                    #else:
                elif cmdargs.split_all_theorems and tok.macroName == 'newtheorem':
                    obj = amsthm.newtheorem()
                    obj.parse(thetex)
                    out_list[-1].write(obj.source)
                    logger.info('adding to splited environments: %r' % obj.source)
                    th = new_theorem(obj.attributes, thedocument, thecontext)
                    name = obj.attributes['name']
                    cmdargs.split_environment.append(name)
                    thecontext.addGlobal(name, th)
                    del th
                elif tok.macroName in ("input","include"):
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                        # only follow local files
                        #inputfile = thetex.kpsewhich(inputfile)
                    else:
                        inputfile = thetex.readArgument(type=str)
                    newoutput = named_stream(blobs_dir,'File',depth,parent=out_list[-1])
                    newoutput.add_metadata(r'\originalFileName',inputfile)
                    out_list.append(newoutput)
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
                    depth.append(tok.macroName)
                    thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
                    del a
                    thetex.input(open(inputfile), Tokenizer=TokenizerPassThru.TokenizerPassThru)
                elif tok.macroName == specialblobinatorEOFcommand:
                    pops_sections()
                    # pops the output when it ends
                    r = out_list[-1].writeout()
                    logger.info('end input, writing %r',r)
                    out_list.pop()
                    a = depth.pop()
                    out_list[-1].write('\\%s{%s}' % (a,r))
                    assert a in ('input','include')
                elif not in_preamble and cmdargs.copy_graphicx \
                     and tok.macroName == "includegraphics":
                    if use_plastex_parse:
                        obj = graphicx.includegraphics()
                        a = obj.parse(thetex)
                        inputfile = a['file']
                        a = obj.source
                        j = a.index('{')
                        c = a[:j]
                        del a, obj
                    else:
                        c = ''
                        for spec in '*','[]',None: 
                            output, source = thetex.readArgumentAndSource(spec=spec)
                            if spec:
                                c += source
                            else:
                                inputfile = source[1:-1]
                    assert isinstance(inputfile,str)
                    assert not os.path.isabs(inputfile)
                    for ext in ['','.png','.jpg','.jpeg','.gif','.pdf','.ps','.eps', None]:
                        if ext is not None:
                            f = osjoin(input_basedir,inputfile+ext)
                            if os.path.isfile(f):
                                inputfile += ext
                                break
                    assert ext is not None, 'graphicx file %r not found' % inputfile
                    u = new_uuid(blobs_dir=blobs_dir)
                    d = uuid_to_dir(u, blobs_dir=blobs_dir, create=True)
                    f = osjoin(d,'blob'+ext)
                    logger.info(' copying %r to %r' % (inputfile,f) )
                    shutil.copy(osjoin(input_basedir,inputfile),osjoin(blobs_dir,f))
                    open(osjoin(blobs_dir,d,"metadata"),'w').write('\\originalFileName{%s}\n\extension{%s}' % (inputfile,ext))
                    out_list[-1].write('\includegraphics'+c+'{'+f+'}')
                    del u,d,f,c,ext,inputfile
                elif tok.macroName == "item" and depth[-1] in cmdargs.split_list :
                    r = out_list[-1].writeout()
                    logger.info('end item, writing %r',r)
                    out_list.pop()
                    out_list[-1].write('\\input{%s}\\item' % (r,))
                    _,source = thetex.readArgumentAndSource('[]')
                    if source:
                        out_list[-1].write(source)
                    out_list.append(named_stream(blobs_dir,depth[-1],depth,parent=out_list[-1]))
                elif tok.macroName == "begin":
                    name = mytex.readArgument(type=str)
                    if name == 'document':
                        in_preamble = False
                        if cmdargs.split_preamble:
                            old = depth.pop()
                            assert old == 'Preamble', " in preamble, the element %r does not match" % old
                            r = out_list[-1].writeout()
                            os_rel_symlink(r,'preamble.tex', cmdargs.blobs_dir ,
                                           target_is_directory=False, force=True)
                            out_list.pop()
                            out_list[-1].write(r'\input{%s}' % r)
                    if not in_preamble:
                        depth.append('\\begin{'+name+'}')
                    out_list[-1].write(r'\begin{%s}' % name)
                    if not in_preamble and name in cmdargs.split_environment :
                        obj = thedocument.createElement(name)
                        obj.macroMode = Command.MODE_BEGIN
                        obj.ownerDocument = thedocument
                        if isinstance(obj, amsthm.theoremCommand):
                            _,source = thetex.readArgumentAndSource('[]')
                            if source:
                                out_list[-1].write(source)
                        #out = obj.invoke(tex) mangles everything
                        #if out is not None:
                        #    obj = out
                        logger.info( 'will split \\begin{%r}' % (name,) )
                        out_list.append(named_stream(blobs_dir,name,depth,parent=out_list[-1]))
                    elif not in_preamble and name in cmdargs.split_list :
                        logger.debug( ' will split items out of \\begin{%r}' % (name,) )
                        t = next(itertokens)
                        while t is not None:
                            # checkme, tok.source may be messing up with comments,
                            out_list[-1].write(t.source)
                            if isinstance(t, plasTeX.Tokenizer.EscapeSequence):
                                if t.macroName == "item":
                                    _,s = thetex.readArgumentAndSource(spec='[]')
                                    if s:
                                        out_list[-1].write(s)
                                    t = None
                                else:
                                    logger.critical('cannot parse %r inside %r' % (t.source,name) )
                                    t = next(itertokens)
                            else:
                                logger.debug('passing %r inside %r' % (t.source,name) )
                                t = next(itertokens)
                        out_list.append(named_stream(blobs_dir,name,depth,parent=out_list[-1]))
                    elif not in_preamble:
                        logger.debug( ' will not split \\begin{%r}' % (name,) )
                    else:
                        logger.info( ' ignore \\begin{%r} in preamble' % (name,) )
                elif tok.macroName == "end":
                    name = thetex.readArgument(type=str)
                    if not in_preamble:
                        if name in ('document','Filesave'):
                            pops_sections()
                        old = depth.pop()
                        assert ('\\begin{'+name+'}') == old , \
                               (' nesting error, %s ended by  \\end{%s}' % (old,name))
                    if not in_preamble and \
                       (name in cmdargs.split_environment or name in cmdargs.split_list):
                        obj = thedocument.createElement(name)
                        obj.macroMode = Command.MODE_END
                        obj.ownerDocument = thedocument
                        out = obj.invoke(thetex)
                        if out is not None:
                            obj = out
                        r = out_list[-1].writeout()
                        if name == 'document':
                            os_rel_symlink(r,'document.tex', cmdargs.blobs_dir ,
                                           target_is_directory=False, force=True)
                        out_list.pop()
                        out_list[-1].write(r'\input{%s}' % r)
                        logger.info( 'did split \\end{%r} into %r' % (name,r) )
                    elif not in_preamble:
                        logger.debug( ' did not split \\end{%r}' % (name,) )
                    else:
                        logger.info( ' ignore \\end{%r} in preamble' % (name,) )
                    out_list[-1].write(r'\end{%s}' % name)
                elif not in_preamble and \
                     tok.macroName in cmdargs.metadata_command :
                    obj = thetex.ownerDocument.createElement(tok.macroName)
                    args = [ thetex.readArgumentAndSource(type=str)[1] for j in range(obj.nargs)]
                    #obj.parse(thetex)
                    logger.info('metadata %r  %r' % (tok,args))
                    for j in args:
                        j =  j.translate({'\n':' '})
                        out_list[-1].add_metadata('\\'+tok.macroName,j)
                    out_list[-1].write(obj.source+''.join(args))
                else:
                    #logger.debug(' unprocessed %r', tok.source)
                    out_list[-1].write(tok.source)
            else:
                out_list[-1].write(str(tok))
        pops_sections()
        # main
        M = out_list.pop()
        r = M.writeout()
        if not out_list:
            os_rel_symlink(r, 'main.tex', cmdargs.blobs_dir ,
                           target_is_directory=False, force=True)
        if depth :
            logger.critical(' depth is %r' % depth)
    except:
        raise
    finally:
        while out_list:
            logger.critical('writing orphan output')
            out_list.pop().writeout()


if __name__ == '__main__':
    print(sys.argv)
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
    parser.add_argument('--metadata-command','--MC',action='append',help='store the argument of this TeX command as metadata for the blob (\\label, \\uuid are always metadata)', default = [])
    parser.add_argument('--split-all-theorems','--AT',action='store_true',help='split any theorem defined by \\newtheorem in a separate blob, as if each theorem was specified by --split-environment ')
    parser.add_argument('--copy-graphicx','--CG',action='store_true',help='copy graphicx as blobs')
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

    MC = [ 'label' ]
    if args.EDB :
        MC += ['difficulty','index','notes', \
                 'keywords', 'prerequisites',  'difficulty','indexiten']
    for name in MC :
        n = 1 if name != r'\indexiten' else 2
        d =  '\\' + name + '{#1}'
        #mycontext.newcommand(name, n, d)
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':n, 'opt':None, 'definition':d})
        assert newclass.nargs == n
        mycontext.addGlobal(name, newclass)
        args.metadata_command.append(name)

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

    for j in 'UUIDs', 'SECs':
        d = osjoin(args.blobs_dir,j)
        if not os.path.isdir(d):
            os.mkdir(d)


    logger.info("processing %r" % input_file)
    blob_inator(input_file, mytex, mydocument, mycontext, args)
    logger.info("end of file")


