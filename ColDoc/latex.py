#!/usr/bin/python3

"""Usage: %(arg0)s [CMD] [OPTIONS]

Create PDF version of a blob

    blob BLOBS_DIR UUID [LANGUAGE]
       convert the blob UUID in BLOBS_DIR,
       if LANGUAGE is not specified , for all languages
    
    all BLOBS_DIR [UUID]
       convert all the blobs in BLOBS_DIR, starting from UUID (default: `main`)
"""

import os,sys,shutil,subprocess

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
\def\uuidbaseurl{%(urlhostport)s%(urlUUIDbasepath)s}
\input{preamble.tex}
\usepackage{ColDocUUID}
\begin{document}
\input{%(input)s}
\end{document}
"""

preview_template=r"""\documentclass{article}
\def\uuidbaseurl{%(urlhostport)s%(urlUUIDbasepath)s}
\input{preamble.tex}
\usepackage{ColDocUUID}
\usepackage[active,tightpage]{preview}
\setlength\PreviewBorder{5pt}
\begin{document}
\input{%(input)s}
\end{document}
"""




def latex_uuid(blobs_dir, uuid, lang=None, metadata=None, warn=True):
    " `latex` the blob identified `uuid`; if `lang` is None, `latex` all languages; ( `metadata` are courtesy , to avoid recomputing )"
    if metadata is None:
        uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir)
    else:
        uuid_dir = None
    #
    if metadata['environ'][0] == 'preamble':
        if warn: logger.warning('Cannot `pdflatex` preamble')
        return True
    if metadata['environ'][0] == 'E_document':
        if warn: logger.warning('Do not need to `pdflatex` this `document` blob, refer the main blob')
        return True
    #
    if lang is not None:
        langs=[lang]
    else:
        langs=metadata['lang']
    #
    res = True
    for l in langs:
        res = res and latex_blob(blobs_dir, metadata=metadata, lang=l, uuid=uuid, uuid_dir=uuid_dir)
    return res

def  latex_blob(blobs_dir, metadata, lang, uuid=None, uuid_dir=None):
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
    save_abs_name = os.path.join(blobs_dir, uuid_dir, 'view' + _lang)
    #
    fake_name = 'fakelatex' + _lang + '_' + uuid
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    #
    D = {'uuiddir':uuid_dir, 'lang':lang, 'uuid':uuid,
         '_lang':_lang,
         'urlhostport':'http://localhost:8000/', 'urlUUIDbasepath':'UUID/',
         'input':os.path.join(uuid_dir,'blob'+_lang+'.tex')}
    #
    if metadata['environ'][0] == 'main_file':
        shutil.copy(os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex'), fake_abs_name+'.tex')
    else:
        main_file = open(fake_abs_name+'.tex', 'w')
        main_file.write(standalone_template % D)
        main_file.close()
    #
    return latex_engine(blobs_dir, fake_abs_name, save_abs_name)

def latex_engine(blobs_dir, fake_abs_name, save_abs_name):
    # FIXME this is not perfect
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
    cwd_ , fake_name =  os.path.split(fake_abs_name)
    assert cwd_ == blobs_dir
    #
    args = ['pdflatex','-file-line-error','-interaction','batchmode',
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
        logger.warning('`pdflatex` fails, see %r'%(save_abs_name+'.log'))
    for e in extensions:
        if os.path.exists(save_abs_name+e):
            os.rename(save_abs_name+e,save_abs_name+e+'~')
        if os.path.exists(fake_abs_name+e):
            if e == '.pdf':
                s=os.path.getsize(fake_abs_name+e)
                logger.info("Created pdf %r size %d"%(save_abs_name+e,s))
            os.rename(fake_abs_name+e,save_abs_name+e)
        else:
            if e=='.toc':
                logger.debug("Missing :%r"%(fake_abs_name+e,))
            else:
                logger.warning("Missing :%r"%(fake_abs_name+e,))
                if e=='.pdf': res=False
    return res


def latex_tree(blobs_dir, uuid=None, lang=None, warn=False):
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
        latex_uuid(blobs_dir, uuid=uuid, metadata=metadata, lang=lang, warn=warn)
    for u in metadata.get('child_uuid',[]):
        latex_tree(blobs_dir, uuid=u, lang=lang, warn=warn)



def main(argv):
    if len(argv)<3 or argv[1] not in ('blob','all'):
        sys.stderr.write(__doc__%{'arg0':argv[0]})
        sys.exit(1)
    blobs_dir = argv[2]
    assert os.path.isdir(blobs_dir), blobs_dir
    logger.setLevel(logging.INFO)
    if argv[1] == 'blob':
        UUID = argv[3]
        lang = None
        if len(argv)>4:
            lang = argv[4]
        latex_uuid(blobs_dir,UUID,lang)
    elif argv[1] == 'all':
        UUID =  None if len(argv) <= 3 else  argv[3]
        latex_tree(blobs_dir,UUID)


if __name__ == '__main__':
    main(sys.argv)

