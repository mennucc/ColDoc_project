#!/usr/bin/python3

""" the DeBlob Inator
joins the blobs to rebuild the original stuff
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

########################################

def deblob_inator_recurse(blob_uuid, thetex, cmdargs, output_file, internal_EOF=True):
    logger.debug("starting uuid %r into %r"%(blob_uuid,output_file))
    use_plastex_parse = True
    blobs_dir=cmdargs.blobs_dir
    #
    specialblobinatorEOFcommand='specialblobinatorEOFcommandEjnjvreAkje'
    def write_special_EOF():
        a=io.StringIO()
        a.write('\\'+specialblobinatorEOFcommand)
        a.seek(0)
        a.name='specialblobinatorEOFcommand'
        thetex.input(a, Tokenizer=TokenizerPassThru.TokenizerPassThru)
        del a
    #
    if internal_EOF:
        write_special_EOF()
    #
    input_file, _, metadata, lang, ext = choose_blob(uuid=blob_uuid, blobs_dir=blobs_dir)
    thetex.input(open(input_file), Tokenizer=TokenizerPassThru.TokenizerPassThru)
    #
    itertokens = thetex.itertokens()
    n=0
    try:
        for tok in itertokens:
            n += len(tok.source)
            if isinstance(tok, plasTeX.Tokenizer.Comment):
                a = tok.source
                if hasattr(plasTeX.Tokenizer.Comment,'source'):
                    # my patch adds 'source' to Comment, so that '%' is already prepended
                    assert a[0] == '%'
                    output_file.write(a)
                else:
                    output_file.write('%'+a)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                macroname = str(tok.macroName)
                #print('>>',macroname)
                if  macroname in ("input","include"):
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                    else:
                        inputfile = thetex.readArgument(type=str)
                    if inputfile[:5] != 'UUID/':
                        logger.error("There should not be an %s{%s}" %(macroname,inputfile))
                        output_file.write('\\'+macroname+'{'+inputfile+'}')
                    else:
                        # blob_inator adds an empty comment after it, here we delete it
                        if macroname == 'input' and ColDoc_commented_newline_after_blob_input:
                            cmt = next(itertokens)
                            if not isinstance(cmt, plasTeX.Tokenizer.Comment):
                                logger.info('Missing comment after %r','\\'+macroname+'{'+inputfile+'}')
                                thetex.pushToken(cmt)
                            else:
                                a = cmt.source
                                if a not in ('','%','\n','%\n'):
                                    logger.info('Nonempty comment after %r','\\'+macroname+'{'+inputfile+'}')
                                    thetex.pushToken('%'+a)
                        #
                        d = os.path.dirname(inputfile)
                        submetadata = Metadata.open(osjoin(blobs_dir, d, 'metadata'))
                        subuuid = submetadata['uuid'][0]
                        sub_output = output_file
                        if 'original_filename' not in submetadata:
                            logger.debug("This \\%s{%s} does not have an `original_filename`" %(macroname,inputfile))
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%start_uuid=%s\n"%(subuuid,))
                            deblob_inator_recurse(subuuid, thetex, cmdargs, output_file)
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%end_uuid=%s\n"%(subuuid,))
                        else:
                            s = submetadata['original_filename']
                            assert len(s) == 1
                            s = s.pop()
                            logger.debug("This \\%s{%s} does have  `original_filename=%r`" %(macroname,inputfile,s))
                            a = os.path.basename(s)
                            if a != s or '..' in s or os.path.isabs(s):
                                logger.warning("Saving %r as %r",s,a)
                            s = a
                            output_file.write('\\'+macroname+'{'+s+'}')
                            if s[-4:] != '.tex':
                                s += '.tex'
                            a = osjoin(cmdargs.latex_dir,s)
                            if os.path.exists(a) and not args.overwrite:
                                raise ColDocException("will not overwrite: %r"%a)
                            sub_output = open(a,"w")
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%start_uuid=%s\n"%(subuuid,))
                            if cmdargs.add_UUID:
                                sub_output.write("\\uuid{%s}%%\n"%(subuuid,))
                            deblob_inator_recurse(subuuid, thetex, cmdargs, sub_output)
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%end_uuid=%s\n"%(subuuid,))
                            sub_output.close()
                            del sub_output
                elif macroname == specialblobinatorEOFcommand:
                    logger.debug("internal EOF")
                    break
                elif macroname == "begin":
                    name = mytex.readArgument(type=str)
                    #print('>>>',name)
                    if name in cmdargs.verbatim_environment:
                        class MyVerbatim(Base.verbatim):
                            macroName = name
                        obj = MyVerbatim()
                        obj.ownerDocument = thetex.ownerDocument
                        t = obj.invoke(thetex)
                        # the above pushes the \end{verbatim} back on stack
                        next(itertokens)
                        output_file.write('\\begin{%s}' % name)
                        for j in t[1:]:
                            output_file.write(j)
                        output_file.write('\\end{%s}' % name)
                        logger.debug('verbatim %r',t)
                        del obj,j,t
                    else:
                        output_file.write('\\%s{%s}'%(macroname,name))
                elif macroname == 'verb':
                    obj = Base.verb()
                    obj.ownerDocument = thetex.ownerDocument
                    t = obj.invoke(thetex)
                    output_file.write('\\verb')
                    for j in t[1:]:
                        output_file.write(j)
                    del obj,j,t
                elif macroname == "includegraphics":
                    # not in_preamble and cmdargs.copy_graphicx \
                    logger.warning("\\includegraphics unimplemented, TODO")
                    output_file.write(tok.source)
                else:
                    output_file.write(tok.source)
            else:
                output_file.write(str(tok))
    except:
        raise
    logger.debug("ending uuid %r into %r"%(blob_uuid,output_file))

#####################à

def deblob_inator(blob_uuid, thetex, cmdargs):
    assert os.path.isdir(cmdargs.blobs_dir), '`blobs-dir` is not a dir: %r' % cmdargs.blobs_dir
    assert os.path.isdir(cmdargs.latex_dir), '`latex-dir` is not a dir: %r' % cmdargs.latex_dir
    #
    filename = 'main.tex'
    #
    a = osjoin(cmdargs.blobs_dir, '.blob_inator-args.json')
    if os.path.isfile(a):
        with open(a) as a:
            oldargs = json.load(a)
        cmdargs.verbatim_environment = oldargs['verbatim_environment']
        filename = os.path.basename(oldargs['input_file'])
    else:
        cmdargs.verbatim_environment = ['verbatim']
        logger.error("File with `blob_inator` parameters is missing?? %r",a)
    #
    a= osjoin(args.latex_dir,filename)
    if os.path.exists(a) and not args.overwrite:
        raise ColDocException("will not overwrite: %r"%a)
    O = open(a,"w")
    #
    return deblob_inator_recurse(blob_uuid, thetex, cmdargs, O, internal_EOF=False)

##############à

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Join the blobs into the original LaTeX input',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--blobs-dir',type=str,default=ColDoc_as_blobs,\
                        help='directory where the blob_ized input tree is',\
                        required=(ColDoc_as_blobs is None))
    parser.add_argument('--latex-dir',type=str,
                        help='directory where the LaTeX files are rebuilt',\
                        required=True) #(ColDoc_as_chunks is None))
                        #default=ColDoc_as_chunks
    parser.add_argument('--root-uuid',type=str,
                        help="uuid of the root node of the blob tree", default=int_to_uuid(1))
    parser.add_argument('--overwrite',action='store_true', help="overwrite existing files")
    parser.add_argument('--add-UUID-comments','--AUC',
                        action='store_true', help="add comments to mark beg/end of blobs")
    parser.add_argument('--add-UUID','--AU',
                        action='store_true', help="add \\uuid{UUID} commands")
    parser.add_argument('--verbose','-v',action='count',default=0)
    #
    args = parser.parse_args()
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
    mytex = TeX()
    #
    try:
        deblob_inator(args.root_uuid, mytex, args)
    except:
        logger.exception(__name__+' failed!')
        sys.exit(1)



