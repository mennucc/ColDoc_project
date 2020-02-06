#!/usr/bin/env python3

"""Usage: %(arg0)s [-v] --blobs-dir BLOBS_DIR  CMD [OPTIONS]

Create PDF version of a blob

    blob  UUID [LANGUAGE]
       convert the blob UUID in BLOBS_DIR,
       if LANGUAGE is not specified , for all languages
    
    all  [UUID]
       convert all the blobs in BLOBS_DIR, starting from UUID (default: `main`)
"""

import os, sys, shutil, subprocess, json, argparse

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
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)


############## ColDoc stuff

#from ColDoc import config, utils
import ColDoc, ColDoc.utils, ColDoc.config


import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base

from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Packages import amsthm , graphicx

# the package ColDocUUID.sty defines a LaTeX command \uuid , that can be overriden in the preamble


standalone_template=r"""\documentclass[varwidth]{standalone}
\def\uuidbaseurl{%(url_UUID)s}
\input{preamble.tex}
\usepackage{ColDocUUID}
\begin{document}
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""

preview_template=r"""\documentclass{article}
\def\uuidbaseurl{%(url_UUID)s}
\input{preamble.tex}
\usepackage{ColDocUUID}
\usepackage[active,tightpage]{preview}
\setlength\PreviewBorder{5pt}
\begin{document}
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""

plastex_template=r"""\documentclass{article}
\def\uuidbaseurl{%(url_UUID)s}
\input{preamble.tex}
\usepackage{hyperref}
\usepackage{ColDocUUID}
\begin{document}
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""


def latex_uuid(blobs_dir, uuid, lang=None, metadata=None, warn=True, options = {}):
    " `latex` the blob identified `uuid`; if `lang` is None, `latex` all languages; ( `metadata` are courtesy , to avoid recomputing )"
    if metadata is None:
        uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir)
    else:
        uuid_dir = None
    #
    if metadata['environ'][0] in ( 'preamble' , 'input_preamble' , 'include_preamble', 'usepackage'):
        ## 'include_preamble' is maybe illegal LaTeX; 'usepackage' is not yet implemented
        if warn: logger.warning('Cannot `pdflatex` preamble')
        return True
    if metadata['environ'][0] == 'E_document':
        if warn: logger.warning('Do not need to `pdflatex` this `document` blob, refer the main blob')
        return True
    #
    if lang is not None:
        langs=[lang]
    else:
        langs=metadata.get('lang',[])
    if not langs:
        logger.debug('No languages for blob %r in blobs_dir %r',uuid,blobs_dir)
        return True
    #
    res = True
    for l in langs:
        res = res and latex_blob(blobs_dir, metadata=metadata, lang=l,
                                 uuid=uuid, uuid_dir=uuid_dir, options = options)
    return res

def  latex_blob(blobs_dir, metadata, lang, uuid=None, uuid_dir=None, options = {}):
    " `latex` the blob identified by the `metadata`, for the given language `lang`. ( `uuid` and `uuid_dir` are courtesy , to avoid recomputing )"
    if uuid is None:
        uuid = metadata.uuid
    if uuid_dir is None:
        uuid_dir = ColDoc.utils.uuid_to_dir(uuid, blobs_dir=blobs_dir)
    #
    if lang is None or lang == '':
        _lang=''
    else:
        _lang = '_' + lang
    #
    # note that extensions are missing
    save_name = os.path.join(uuid_dir, 'view' + _lang)
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_name = 'fakelatex' + _lang + '_' + uuid
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    #
    D = {'uuiddir':uuid_dir, 'lang':lang, 'uuid':uuid,
         '_lang':_lang,
         'begin':'','end':'',
         'url_UUID' : options['url_UUID'],
         'input':os.path.join(uuid_dir,'blob'+_lang+'.tex')}
    #
    environ = metadata['environ'][0]
    if environ[:2] == 'E_' and environ not in ( 'E_document', ):
        env = environ[2:]
        D['begin'] = r'\begin{'+env+'}'
        D['end'] = r'\end{'+env+'}'
        if 'split_list' in options and env in options['split_list']:
            D['begin'] += r'\item'
    ##
    ## create pdf
    if metadata['environ'][0] == 'main_file':
        shutil.copy(os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex'), fake_abs_name+'.tex')
    else:
        main_file = open(fake_abs_name+'.tex', 'w')
        main_file.write(standalone_template % D)
        main_file.close()
    rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, options)
    ##
    ## create html
    if environ == 'main_file':
        D['input'] = 'document.tex'
    main_file = open(fake_abs_name+'.tex', 'w')
    main_file.write(plastex_template % D)
    main_file.close()
    rh = plastex_engine(blobs_dir, fake_name, save_name, environ, options)
    return rh and rp



def plastex_engine(blobs_dir, fake_name, save_name, environ, options):
    " compiles the `fake_name` latex, and generates the `save_name` result ; note that extensions are missing "
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    #
    for e in ('.paux',):
        if os.path.exists(save_abs_name+'_plastex'+e):
            shutil.copy(save_abs_name+'_plastex'+e,fake_abs_name+e)
    #
    import glob, string
    import plasTeX
    from plasTeX.TeX import TeX
    #from plasTeX.Config import config
    from plasTeX.Config import config as plastex_config
    #from plasTeX.ConfigManager import *
    import plasTeX.ConfigManager
    #from plasTeX.Logging import getLogger, updateLogLevels
    #
    F = fake_name+'.tex'
    d = os.path.dirname(F)
    #assert os.path.isfile(F),F
    if d :
        logger.warning("The argument of `plastex` is not in the blobs directory: %r", F)
    #
    n =  osjoin(blobs_dir,save_name+'_paux')
    if not os.path.isdir(n):    os.mkdir(n)
    #
    argv = ['-d',save_name+'_html',"--renderer=HTML5",]
    if environ != 'main_file':
        argv += '--no-display-toc',
    argv += ['--log','--paux-dirs',save_name+'_paux',F]
    ret = ColDoc.utils.plastex_invoke(cwd_ =  blobs_dir ,
                         stdout_  = open(osjoin(blobs_dir,save_name+'_plastex.stdout'),'w'),
                         argv_ = argv )
    extensions = '.log','.paux','.tex'
    for e in extensions:
        if os.path.exists(save_abs_name+'_plastex'+e):
            os.rename(save_abs_name+'_plastex'+e,save_abs_name+'_plastex'+e+'~')
        if os.path.exists(fake_abs_name+e):
            os.rename(fake_abs_name+e,save_abs_name+'_plastex'+e)
    if ret :
        logger.warning('Failed: cd %r ; plastex %s',blobs_dir,' '.join(argv))
    if os.path.isfile(osjoin(blobs_dir, save_name+'_html','index.html')):
        logger.info('created html version of %r ',save_abs_name)
    else:
        logger.warning('no "index.html" in %r',save_name+'_html')
        return False
    return ret == 0


def pdflatex_engine(blobs_dir, fake_name, save_name, environ, options):
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    # FIXME this is not perfect: 'main.aux' is created only when the
    # 'main_file' or 'document' blob is compiled; moreover it is not working
    a = os.path.join(blobs_dir,'main.aux')
    if os.path.exists(a):
        logger.debug("Re-using %r",a)
        shutil.copy2(a,fake_abs_name+'.aux')
    elif os.path.exists(save_abs_name+'.aux'):
        logger.debug("Re-using %r",save_abs_name+'.aux')
        shutil.copy2(save_abs_name+'.aux', fake_abs_name+'.aux')
    else:
        logger.debug("No aux file for this job")
    #
    extensions = '.tex','.log','.pdf','.aux','.toc','.out'
    #
    for e in extensions:
        if e not in ('.tex','.aux') and os.path.exists(fake_abs_name+e):
            logger.warning('Overwriting: %r',fake_abs_name+e)
    #
    engine = options.get('latex_engine','pdflatex')
    logger.debug('Using engine %r',engine)
    args = [engine,'-file-line-error','-interaction','batchmode',
            fake_name+'.tex']
    #
    p = subprocess.Popen(args,cwd=blobs_dir,stdin=open(os.devnull),
                         stdout=open(os.devnull,'w'),stderr=subprocess.STDOUT)
    r=p.wait()
    res = False
    if r == 0:
        p = subprocess.Popen(args,cwd=blobs_dir,stdin=open(os.devnull),
                             stdout=open(os.devnull,'w'),stderr=subprocess.STDOUT)
        p.wait()
        if r == 0 :
            res = True
    else:
        logger.warning('%r fails, see %r'%(engine,save_abs_name+'.log'))
    for e in extensions:
        if os.path.exists(save_abs_name+e):
            os.rename(save_abs_name+e,save_abs_name+e+'~')
        if os.path.exists(fake_abs_name+e):
            if e == '.pdf':
                s=os.path.getsize(fake_abs_name+e)
                logger.info("Created pdf %r size %d"%(save_abs_name+e,s))
            if e == '.aux' and environ in ( 'main_file', 'E_document'):
                # keep a copy of the aux file
                shutil.copy(fake_abs_name+e, osjoin(blobs_dir,'main.aux'))
            os.rename(fake_abs_name+e,save_abs_name+e)
        else:
            if e=='.toc':
                logger.debug("Missing :%r"%(fake_abs_name+e,))
            else:
                logger.warning("Missing :%r"%(fake_abs_name+e,))
                if e=='.pdf': res=False
    return res


def latex_tree(blobs_dir, uuid=None, lang=None, warn=False, options={}):
    " latex the whole tree, starting from `uuid` "
    if uuid is None:
        uuid = '001'
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir)
    #
    if metadata['environ'][0] == 'preamble':
        if warn: logger.warning('Cannot `pdflatex` preamble , UUID = %r'%(uuid,))
    elif metadata['environ'][0] == 'E_document':
        if warn: logger.warning('Do not need to `pdflatex` the `document` blob , UUID = %r , refer the main blob'%(uuid,))
    else:
        latex_uuid(blobs_dir, uuid=uuid, metadata=metadata, lang=lang, warn=warn, options=options)
    for u in metadata.get('child_uuid',[]):
        latex_tree(blobs_dir, uuid=u, lang=lang, warn=warn, options=options)




def prepare_parser(uses_django=False):
    # parse arguments
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser = argparse.ArgumentParser(description='Compile coldoc material, using `latex` and `plastex` ',
                                     epilog=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--blobs-dir',type=str,\
                        help='directory where the blob_ized output is saved',
                        required=(not uses_django))
    parser.add_argument('--url-UUID',type=str,\
                        help='URL of the website that will show the UUIDs, used by my \\uuid macro',
                        required=(not uses_django))
    parser.add_argument('command', help='specific command',nargs='+')
    return parser

def main(argv):
    parser = prepare_parser()
    args = parser.parse_args()
    #
    if args.command[0] not in ('blob','all','main'):
        sys.stderr.write(__doc__%{'arg0':arg0})
        sys.exit(1)
    #
    blobs_dir = args.blobs_dir
    assert os.path.isdir(blobs_dir), blobs_dir
    #
    coldoc_dir = os.path.dirname(blobs_dir)
    a = osjoin(coldoc_dir, 'coldoc.json')
    options = {}
    if os.path.isfile( a ):
        coldoc = json.load(open(a))
        options = coldoc['fields']
        logger.debug('From %r options %r',a,options)
    else:
        logger.debug('No %r',a)
    #
    a = osjoin(blobs_dir, '.blob_inator-args.json')
    if os.path.isfile( a ):
        blob_inator_args = json.load(open(a))
        assert isinstance(blob_inator_args,dict)
        options.update(blob_inator_args)
        logger.debug('From %r options %r',a,options)
    else:
        logger.debug('No %r',a)
    return main_by_args(args,options)


def main_by_args(args,options):
    argv = args.command
    blobs_dir = args.blobs_dir
    logger.setLevel(logging.WARNING)
    if args.verbose > 1 :
        logger.setLevel(logging.DEBUG)
    elif args.verbose > 0 :
        logger.setLevel(logging.INFO)
    #
    options['url_UUID'] = args.url_UUID
    if argv[0] == 'blob':
        UUID = argv[1]
        lang = None
        if len(argv)>2:
            lang = argv[2]
        latex_uuid(blobs_dir,UUID,lang=lang, options=options)
    elif argv[0] == 'all':
        UUID =  None if len(argv) <= 1 else  argv[1]
        latex_tree(blobs_dir,UUID, options=options)


if __name__ == '__main__':
    main(sys.argv)

