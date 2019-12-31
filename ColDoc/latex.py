#!/usr/bin/python3

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

standalone_template=r"""\documentclass[varwidth]{standalone}
\input{preamble.tex}
\begin{document}
\input{%(input)s}
\end{document}
"""

preview_template=r"""\documentclass{article}
\input{preamble.tex}
\usepackage[active,tightpage]{preview}
\setlength\PreviewBorder{5pt}
\begin{document}
\input{%(input)s}
\end{document}
"""




def latex(blobs_dir,UUID,lang):
    if lang is not None:
        lang='_'+lang
    else:
        lang=''
    #
    extensions = '.tex','.log','.pdf','.aux','.toc'
    #
    uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                   blobs_dir = blobs_dir)
    #
    if metadata['environ'][0] == 'preamble':
        logger.warning('Cannot `pdflatex` preamble')
        return
    if metadata['environ'][0] == 'E_document':
        logger.warning('Do not need to `pdflatex` this `document` blob, refer the main blob')
        return
    #
    
    blob_base_name = os.path.join(blobs_dir, uuid_dir, 'fakelatex'+lang)
    #
    fake_name = 'fakelatex'+lang+'_'+UUID
    main_base_name = os.path.join(blobs_dir, fake_name)
    #
    D = {'uuiddir':uuid_dir, 'lang':lang, 'uuid':uuid,
         'input':os.path.join(uuid_dir,'blob'+lang+'.tex')}
    #
    for e in extensions:
        if os.path.exists(main_base_name+e):
            logger.warning('Overwriting: %r',main_base_name+e)
    if os.path.exists(blob_base_name+'.aux'):
        shutil.copy2(blob_base_name+'.aux',main_base_name+'.aux')
    if metadata['environ'][0] == 'main_file':
        shutil.copy(os.path.join(blobs_dir, uuid_dir, 'blob'+lang+'.tex'),main_base_name+'.tex')
    else:
        main_file = open(main_base_name+'.tex','w')
        main_file.write(standalone_template % D)
        main_file.close()
    
    args = ['pdflatex','-file-line-error','-interaction','batchmode',
            fake_name+'.tex']
    #args = ['/bin/pwd']
    p = subprocess.Popen(args,cwd=blobs_dir)
    r=p.wait()
    if r == 0:
        p = subprocess.Popen(args,cwd=blobs_dir)
        p.wait()
    else:
        logger.warning('UUID %r fails',UUID)
    for e in extensions:
        if os.path.exists(blob_base_name+e):
            os.rename(blob_base_name+e,blob_base_name+e+'~')
        if os.path.exists(main_base_name+e):
            if e == '.pdf':
                s=os.path.getsize(main_base_name+e)
                logger.info("Created pdf %r size %d"%(blob_base_name+e,s))
            os.rename(main_base_name+e,blob_base_name+e)
        else:
            logger.log(logging.DEBUG if e=='.toc' else logging.WARNING,
                       "Missing :%r"%(main_base_name+e,))


if __name__ == '__main__':
    if len(sys.argv)<3:
        sys.stderr.write("Usage: %s blobs_dir uuid [languagecode]\n"%(sys.argv[0]))
        sys.exit(1)
    blobs_dir=sys.argv[1]
    assert os.path.isdir(blobs_dir)
    UUID=sys.argv[2]
    lang = None
    if len(sys.argv)>3:
        lang = sys.argv[3]
    latex(blobs_dir,UUID,lang)
