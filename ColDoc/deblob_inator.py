#!/usr/bin/env python3

""" the DeBlob Inator
joins the blobs to rebuild the original stuff
"""

############## system modules

import itertools, sys, os, io, copy, string, argparse, importlib, shutil, re, json
import os.path
from os.path import join as osjoin


if __name__ == '__main__':
    for j in ('','.'):
        while j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n' % (j,))
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)


############## ColDoc stuff

from ColDoc.config import *

from ColDoc.utils import *

Metadata = FMetadata

#########################################################################
import TokenizerPassThru

import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base

from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Packages import amsthm , graphicx

########################################

def deblob_inator_recurse(blob_uuid, thetex, cmdargs, output_file, recreated_files, internal_EOF=True):
    logger.debug("starting uuid %r into %r"%(blob_uuid,output_file))
    use_plastex_parse = True
    blobs_dir=cmdargs.blobs_dir
    metadata_class = Metadata
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
    F = open(input_file)
    if cmdargs.rm_uuid:
        a = F.readline()
        if not ( a.startswith('\\uuid{') and a.endswith('%\n')):
            F = open(input_file)
    thetex.input(F, Tokenizer=TokenizerPassThru.TokenizerPassThru)
    #
    logger.debug("recreating file:%r"%(recreated_files[-1]))
    #
    itertokens = thetex.itertokens()
    n=0
    try:
        for tok in itertokens:
            n += len(tok.source)
            if isinstance(tok, TokenizerPassThru.Comment):
                a = tok.source
                output_file.write('%'+a)
            elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
                macroname = str(tok.macroName)
                if macroname == 'ColDocUUIDcheckpoint':
                    continue
                if  macroname in ("input","include"):
                    if use_plastex_parse:
                        obj = Base.input()
                        a = obj.parse(thetex)
                        inputfile = a['name']
                    else:
                        inputfile = thetex.readArgument(type=str)
                    # follow one symlink
                    a = osjoin(blobs_dir,inputfile)
                    if  not os.path.exists(a):
                        a += '.tex'
                    if  os.path.islink(a) and not inputfile.startswith('UUID/'):
                        # TODO may not work for subdirectories, checkme
                        l =  os.readlink(a)
                        l = osjoin(os.path.dirname(inputfile),l)
                        if os.path.isfile(osjoin(blobs_dir,l)):
                            logger.warning('\\input follows this link: %r -> %r',inputfile,l)
                            inputfile = l
                            if inputfile.endswith('.tex'):
                                inputfile = inputfile[:-4]
                        else:
                            logger.warning('FIXME cannot follow this link: %r -> %r',inputfile,l)
                    #
                    if inputfile[:4] == 'SEC/':
                        # resolve symlink
                        a,b = os.path.split(inputfile)
                        a = os.readlink(osjoin(blobs_dir,a))
                        assert a[:8] == '../UUID/'
                        #a = os.normpath(osjoin(blobs_dir,a))
                        #a = os.path.relpath(a,blobs_dir)
                        a = a[3:]
                        inputfile = osjoin(a,b)
                        del a,b
                    if inputfile[:5] != 'UUID/':
                        logger.error("There should not be an %s{%s}" %(macroname,inputfile))
                        output_file.write('\\'+macroname+'{'+inputfile+'}')
                    else:
                        # blob_inator adds an empty comment after it, here we delete it
                        if macroname == 'input' and ColDoc_commented_newline_after_blob_input:
                            cmt = next(itertokens)
                            if not isinstance(cmt, TokenizerPassThru.Comment):
                                logger.info('Missing comment after %r','\\'+macroname+'{'+inputfile+'}')
                                thetex.pushToken(cmt)
                            else:
                                a = cmt.source
                                if a not in ('','%','\n','%\n'):
                                    logger.info('Nonempty comment after %r','\\'+macroname+'{'+inputfile+'}')
                                    thetex.pushToken('%'+a)
                        #
                        d = os.path.dirname(inputfile)
                        submetadata = Metadata.load_by_file(osjoin(blobs_dir, d, 'metadata'))
                        subuuid = submetadata['uuid'][0]
                        sub_output = output_file
                        s = submetadata.get('original_filename')
                        assert len(s)<=1, s
                        original_filename = s.pop() if len(s)==1 else None
                        if original_filename and original_filename[0] == '/':
                            # when it is  '/preamble.tex' and '/document.tex', it is a marker, not really a filename
                            original_filename = '' 
                        if  not original_filename:
                            logger.debug("This \\%s{%s} does not have an `original_filename`" %(macroname,inputfile))
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%start_uuid=%s\n"%(subuuid,))
                            deblob_inator_recurse(subuuid, thetex, cmdargs, output_file,
                                                  recreated_files)
                            if cmdargs.add_UUID_comments:
                                sub_output.write("%%end_uuid=%s\n"%(subuuid,))
                        else:
                            s = original_filename
                            logger.debug("This \\%s{%s} does have  `original_filename=%r`" %(macroname,inputfile,s))
                            a = os.path.basename(s)
                            if a != s or '..' in s or os.path.isabs(s):
                                logger.warning("Saving %r as %r",s,a)
                            s = a
                            output_file.write('\\'+macroname+'{'+s+'}')
                            if s[-4:] != '.tex':
                                s += '.tex'
                            a = osjoin(cmdargs.latex_dir,s)
                            if a in recreated_files:
                                logger.debug("file was already recreated:%r"%(a,))
                            else:
                                logger.debug("recursively recreating file:%r"%(a,))
                                recreated_files.append(a)
                                if os.path.exists(a) and not args.overwrite:
                                    raise ColDocException("will not overwrite: %r"%a)
                                sub_output = open(a,"w")
                                if cmdargs.add_UUID_comments:
                                    sub_output.write("%%start_uuid=%s\n"%(subuuid,))
                                #if cmdargs.add_UUID:
                                #    sub_output.write("\\uuid{%s}%%\n"%(subuuid,))
                                deblob_inator_recurse(subuuid, thetex, cmdargs, sub_output,
                                                      recreated_files)
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
                elif macroname in cmdargs.split_graphic+['usepackage','bibliography']:
                    # not in_preamble and cmdargs.copy_graphicx \
                    cmd = src = '\\' + macroname
                    #
                    for spec in '*','[]',None:
                        _, s = thetex.readArgumentAndSource(spec=spec)
                        src += s
                        if spec:
                            cmd += s
                        else:
                            inputfile = s[1:-1]
                    del s
                    #
                    if inputfile.startswith('UUID/'):
                        logger.debug("Reversing: %r", src)
                        sub_uuid_ = dir_to_uuid(os.path.dirname(inputfile))
                        sub_metadata = metadata_class.load_by_uuid(uuid=sub_uuid_,
                                                                   basepath=blobs_dir)
                        sub_uuid_dir = uuid_to_dir(sub_uuid_, blobs_dir=blobs_dir)
                        #
                        orig_cmd = sub_metadata.get('original_command')
                        if orig_cmd:
                            orig_cmd = orig_cmd.pop()
                        logger.debug("original_command: %r", orig_cmd)
                        #
                        #sub_input_file, _, sub_metadata, sublang, subext = \
                        #    choose_blob(uuid = sub_uuid_, blobs_dir=blobs_dir,
                        #                lang = None, ext = None)
                        orig_fln = sub_metadata['original_filename'][0]
                        #
                        orig_langs = sub_metadata.get('lang')
                        if 'mul' in orig_langs:
                            logger.warning('Multiple languages not supported %r',orig_lang)
                        #
                        sub_input_file = osjoin(blobs_dir, sub_uuid_dir, 'blob')
                        orig_ext = sub_metadata.get('extension')
                        #if macroname in cmdargs.split_graphic:
                        #    # strip extensions
                        #    a,b = os.path.splitext(inputfile)
                        #    c,d = os.path.splitext(sub_input_file)
                        #    if b and d and c == d:
                        #        inputfile = a
                        #        sub_input_file = c
                        for ext in orig_ext:
                            if orig_fln.endswith(ext):
                                # TODO this should not happen
                                logger.warning('Stripping extension from %r',orig_fln)
                                orig_fln = orig_fln[:-len(ext)]
                                break
                        for ext in orig_ext:
                          for orig_lang in orig_langs:
                            a = sub_input_file + '_' + orig_lang + ext
                            b = osjoin(cmdargs.latex_dir,orig_fln) + ext
                            if os.path.isfile(a):
                                logger.info('Copy %r -> %r',a,b)
                                os.makedirs(os.path.dirname(b),exist_ok=True)
                                shutil.copy(a,b)
                            else:
                                logger.error('Cannot Copy %r -> %r',a,b)
                        if orig_cmd:
                            output_file.write(orig_cmd)
                        else:
                            # TODO this is not really identical to the original,
                            a = orig_fln
                            output_file.write(cmd+'{'+a+'}')
                            logger.warning('No original command, using %r',cmd+'{'+a+'}')
                    else:
                        logger.debug("Leaving unaltered %r", src)
                        output_file.write(src)
                    del cmd, src, inputfile
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
    if not os.path.exists(cmdargs.latex_dir):
        os.makedirs(cmdargs.latex_dir)
    assert os.path.isdir(cmdargs.latex_dir), '`latex-dir` is not a dir: %r' % cmdargs.latex_dir
    #
    filename = 'main.tex'
    #
    try:
        oldargs = get_blobinator_args(cmdargs.blobs_dir)
        cmdargs.verbatim_environment = oldargs['verbatim_environment']
        cmdargs.split_graphic = oldargs['split_graphic']
        filename = os.path.basename(oldargs['orig_input_file'])
    except:
        cmdargs.verbatim_environment = ['verbatim']
        cmdargs.split_graphic = ["includegraphics"]
        logger.exception("File with `blob_inator` parameters is missing??")
    #
    a= osjoin(args.latex_dir,filename)
    if os.path.exists(a) and not args.overwrite:
        raise ColDocException("will not overwrite: %r"%a)
    O = open(a,"w")
    #
    recreated_files=[a]
    return deblob_inator_recurse(blob_uuid, thetex, cmdargs, O, recreated_files, internal_EOF=False)

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
    #parser.add_argument('--add-UUID','--AU',
    #                    action='store_true', help="add \\uuid{UUID} commands")
    parser.add_argument('--rm-uuid',action='store_true',
                        help="remove the first line of a blob if it is `\\uuid{...}%` ")
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



