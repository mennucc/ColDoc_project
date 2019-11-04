#!/usr/bin/python3

""" the Blob Inator
splits the input into blobs
"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib
import os.path
from os.path import join as osjoin
import logging
from logging import Logger, StreamHandler, Formatter

logger = Logger('blob_inator')
handler = StreamHandler(sys.stderr)
LOG_FORMAT = '[%(name)s] %(levelname)s: %(message)s'
handler.setFormatter(Formatter(LOG_FORMAT))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


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

from plasTeX.Base.LaTeX import  documentclass

from plasTeX.Packages import amsthm

#import plasTeX.Base.LaTeX as LaTeX
#import plasTeX.Base.LaTeX.Environments as Environments

# non funziona
#plasTeX.TeX.Tokenizer = TokenizerPassThru.TokenizerPassThru


######################################################################



class named_stream(io.StringIO):
    " stream with a filename attached, and metadata; data will be written by 'writeout' method"
    _filename = None
    def __init__(self, basepath, environ , depth,
                lang = ColDoc_lang, parent_file = None, extension = '.tex',
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
        if parent_file:
            self.add_metadata(r'\parentFile', parent_file)
        #
        self._uuid = None
        self._filename = None
        # save from gc, for __del__ method
        self._sys = sys
        self._open = open
        self._logger = logger

    def _find_unused_UUID(self):
        " relative to basepath "
        filename = None
        while not filename:
            u = new_uuid(blobs_dir=self._basepath)
            d = uuid_to_dir(u, blobs_dir=self._basepath, create=True)
            self._dir = d
            filename = osjoin(d, 'blob_' + self._lang + self._extension)
            self._uuid = u
            if os.path.exists( osjoin(self._basepath, filename) ):
                logger.warn(' output exists',filename)
                filename = None
        assert not os.path.isabs(filename)
        assert not os.path.exists ( osjoin(self._basepath, filename) )
        self.filename = filename
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
    def filename(self):
        " relative to basepath "
        return self._filename
    @filename.setter
    def filename(self, filename):
        " relative to basepath "
        assert not os.path.isabs(filename)
        self._filename = filename
        self._dir = os.path.dirname(filename)
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
        assert self._filename is not False
        if self._filename is None:
            self._find_unused_UUID()
        filename = osjoin(self._basepath, self._filename)
        metadata_file = osjoin(self._basepath, self._dir, 'metadata')
        if True: #len(self.getvalue()) > 0:
            self.flush()
            logger.info("writeout %r" % self._filename)
            self._open(filename ,'w').write(self.getvalue())
            self._open(metadata_file,'w').write(self._metadata_txt)
            r =  self._filename
            # no more messing with this class
            self._filename = False
            self.close()
            return r
    def __del__(self):
        if self._filename:
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

def blob_inator(input_file, thetex, thedocument, thecontext, cmdargs):
    blobs_dir=cmdargs.blobs_dir
    input_basedir = os.path.dirname(cmdargs.input_file)
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    in_preamble = False
    n = 0
    depth = []
    section_name = None
    thetex.input(open(input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    output = named_stream(blobs_dir,'MainFile',depth)
    output.filename = 'main.tex'
    output.add_metadata(r'\originalFileName',input_file)
    out_list = [output]
    del output
    try:
        for tok in thetex.itertokens():
            n += len(tok.source)
            if isinstance(tok, plasTeX.Tokenizer.Comment):
                out_list[-1].write('%'+tok.source)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                if tok.macroName == 'documentclass':
                    in_preamble = True
                    obj = documentclass()
                    a = obj.parse(thetex)
                    # implement obj.load(thetex, a['name'], a['options'])
                    thecontext.loadPackage(thetex, a['name']+'.cls',
                                           a['options'])
                    out_list[-1].write(obj.source)
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
                    inputfile = thetex.readArgument(type=str)
                    newoutput = named_stream(blobs_dir,'File',depth)
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
                    depth.append('input')
                    thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
                    del a
                    thetex.input(open(inputfile), Tokenizer=TokenizerPassThru.TokenizerPassThru)
                elif tok.macroName == specialblobinatorEOFcommand:
                    # pops the output when it ends
                    r = out_list[-1].writeout()
                    logger.info('end input, writing %r',r)
                    out_list.pop()
                    out_list[-1].write(r'\input{%s}' % r)
                    assert depth.pop() == 'input'
                elif tok.macroName == "begin":
                    name = mytex.readArgument(type=str)
                    if name == 'document':
                        in_preamble = False
                    out_list[-1].write(r'\begin{%s}' % name)
                    if name in cmdargs.split_environment : #thetex.ownerDocument.context.keys():
                        #tex.pushTokens(names)
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
                        newoutput = named_stream(blobs_dir,name,depth)
                        #out_list[-1].write(r'\\inputUUID{%s}' % newoutput.filename)
                        out_list.append(newoutput)
                        del newoutput
                        depth.append(name)
                    else:
                        depth.append(name)
                        logger.debug( ' will not split \\begin{%r}' % (name,) )
                elif tok.macroName == "end":
                    old = depth.pop()
                    name = thetex.readArgument(type=str)
                    assert name == old , (' environ \\begin{%r} does not match \\end{%r}' % (old,name))
                    if name in cmdargs.split_environment: #thetex.ownerDocument.context.keys():
                        #tex.pushTokens(names)
                        obj = thedocument.createElement(name)
                        obj.macroMode = Command.MODE_END
                        obj.ownerDocument = thedocument
                        out = obj.invoke(thetex)
                        if out is not None:
                            obj = out
                        #logger.info('end %r %r %r' % (tok,obj,old))
                        r = out_list[-1].writeout()
                        out_list.pop()
                        out_list[-1].write(r'\input{%s}' % r)
                        logger.info( 'did split \\end{%r} into %r' % (name,r) )
                    else:
                        logger.debug( ' did not split \\end{%r}' % (name,) )
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
        out_list.pop().writeout()
    except:
        raise
    finally:
        while out_list:
            logger.critical('writing output')
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
    parser.add_argument('--metadata-command','--MC',action='append',help='store the argument of this TeX command as metadata for the blob (\\label, \\uuid are always metadata)', default = [])
    parser.add_argument('--split-all-theorems','--AT',action='store_true',help='split any theorem defined by \\newtheorem in a separate blob, as if each theorem was specified by --split-environment ')
    parser.add_argument('--EDB-metadata',action='store_true',help='add EDB metadata to --metadata-command')
    parser.add_argument('--EDB-environment',action='store_true',help='add EDB environments to --split_theorems')
    args = parser.parse_args()
    input_file = args.input_file
    verbose = args.verbose
    assert type(verbose) == int and verbose >= 0
    #hack
    #input_file = '/home/andrea/Work/CORSI/EDB/EDB.tex'
    assert os.path.isdir(args.blobs_dir)
    assert os.path.isfile(input_file)
    input_basedir = os.path.dirname(input_file)

    mycontext = plasTeX.Context.Context(load = False)
    if args.split_sections:
        mycontext.newcommand('section',1,r'\section{#1}')
        mycontext.newcommand('subsection',1,r'\subsection{#1}')

    MC = [ 'label' ]
    if args.EDB_metadata :
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

    args.split_environment.append('document')
    if args.EDB_environment:
        thecounter = 'thmCount'
        mycontext.newcounter(thecounter, initial=0) #, resetby=parent)
        for name in 'Exercise','wipExercise','Definition','Theorem','Example','delasol','Remark':
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


    #mycontext.newenvironment('Theorem', 0, [r'\begingroup\em Thm:', r'\endgroup'])
    #mycontext.newenvironment('extrastuff', 0, [r'\begingroup\em Thm:', r'\endgroup'])
    mycontext.newenvironment('Exercises', 0, [r'\begingroup\em wipExe:', r'\endgroup'])

    mydocument = TeXDocument(context = mycontext)
    mytex = TeX(ownerDocument=mydocument)

    #myfile = open(osjoin(EDB_standard,input_file+'.tex'))

    out = open(osjoin(args.blobs_dir,'main.tex'),'w')

    for j in 'UUIDs', 'SECs':
        d = osjoin(args.blobs_dir,j)
        if not os.path.isdir(d):
            os.mkdir(d)


    logger.info("processing %r" % input_file)
    blob_inator(input_file, mytex, mydocument, mycontext, args)
    logger.info("end of file")


