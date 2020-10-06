#!/usr/bin/env python3

__all__ = ('main_by_args','latex_main','latex_uuid','latex_tree')

cmd_help="""
Command help:

    blob
       convert the blob --uuid=UUID in BLOBS_DIR,
    
    tree
       convert all the blobs in BLOBS_DIR, starting from --uuid=UUID

    main
       convert the whole document

    all
       all of the above
"""

import os, sys, shutil, subprocess, json, argparse, pathlib, tempfile

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

#
ColDoc_latex_engines=[
        ('pdflatex','LaTeX'),
        ('xelatex','XeLaTeX'),
        ('lualatex','LuaLaTeX'),
    ]


#from ColDoc import config, utils
import ColDoc, ColDoc.utils, ColDoc.config, ColDoc.transform


import plasTeX
import plasTeX.TeX, plasTeX.Base.LaTeX, plasTeX.Context , plasTeX.Tokenizer , plasTeX.Base

from plasTeX.TeX import TeX
from plasTeX import TeXDocument, Command

import plasTeX.Base as Base

from plasTeX.Packages import amsthm , graphicx

# the package ColDocUUID.sty defines a LaTeX command \uuid , that can be overriden in the preamble

environments_we_wont_latex = ( 'preamble' , 'input_preamble' , 'include_preamble',
                               'usepackage', 'bibliography' )

standalone_template=r"""\documentclass[varwidth=%(width)s]{standalone}
\def\uuidbaseurl{%(url_UUID)s}
\input{preamble.tex}
\usepackage{ColDocUUID}
\begin{document}
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""

preview_template=r"""\documentclass %(documentclass_options)s {%(documentclass)s}
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
## TODO investigate, this generates an empty PDF
##\setlength\PreviewBorder{5pt}
##%\usepackage[active]{preview}

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
    warn = logging.WARNING if warn else logging.DEBUG
    if metadata is None:
        uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                blobs_dir = blobs_dir,
                                coldoc = options.get('coldoc'),
                                metadata_class= options['metadata_class'])
    else:
        uuid_dir = None
    #
    if metadata.environ in environments_we_wont_latex :
        ## 'include_preamble' is maybe illegal LaTeX; 'usepackage' is not yet implemented
        logger.log(warn, 'Cannot `pdflatex` environ=%r',metadata.environ)
        return True
    #
    if metadata.environ == 'main_file':
        logger.log(warn, 'Do not need to `pdflatex` the main_file')
        return True
    #
    if lang is not None:
        langs=[lang]
    else:
        langs=metadata.get('lang')
    if not langs:
        logger.debug('No languages for blob %r in blobs_dir %r',uuid,blobs_dir)
        return True
    #
    res = True
    retcodes = {}
    for l in langs:
        rh, rp = latex_blob(blobs_dir, metadata=metadata, lang=l,
                            uuid=uuid, uuid_dir=uuid_dir, options = options)
        res = res and rh and rp
        j = (':'+l) if (isinstance(l,str) and l) else ''
        retcodes['latex'+j] = rp
        retcodes['plastex'+j] = rh
    metadata.latex_time_update()
    if res:
        metadata.latex_return_codes = ''
    else:
        metadata.latex_return_codes = json.dumps(retcodes)
    metadata.save()
    return res

def  latex_blob(blobs_dir, metadata, lang, uuid=None, uuid_dir=None, options = {}, squash = True):
    """ `latex` the blob identified by the `metadata`, for the given language `lang`.
    ( `uuid` and `uuid_dir` are courtesy , to avoid recomputing )
    Optionally squashes all sublevels, replacing with \\uuidplaceholder """
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
    if squash is None:
        squash = options.get('squash')
    # note that extensions are missing
    save_name = os.path.join(uuid_dir, 'view' + _lang)
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_texfile = tempfile.NamedTemporaryFile(prefix='fakelatex' + _lang + '_' + uuid + '_',
                                                 suffix='.tex', dir = blobs_dir , mode='w+', delete=False)
    fake_abs_name = fake_texfile.name[:-4]
    fake_name = os.path.basename(fake_abs_name)
    #
    D = {'uuiddir':uuid_dir, 'lang':lang, 'uuid':uuid,
         '_lang':_lang,
         'width':'4in',
         'begin':'','end':'',
         'url_UUID' : options['url_UUID'],
         }
    #
    b = os.path.join(uuid_dir,'blob'+_lang+'.tex')
    s = os.path.join(uuid_dir,'squash'+_lang+'.tex')
    if squash:
        ColDoc.transform.squash_latex(b, s, blobs_dir, options,
                                      helper = options.get('squash_helper')(blobs_dir, metadata, options))
        D['input'] = s
    else:
        D['input'] = b
    #
    environ = metadata.environ
    if environ[:2] == 'E_' and environ not in ( 'E_document', ):
        env = environ[2:]
        D['begin'] = r'\begin{'+env+'}'
        D['end'] = r'\end{'+env+'}'
        if 'split_list' in options and env in options['split_list']:
            D['begin'] += r'\item'
    ##
    ## create pdf
    logger.debug('create pdf for %r',save_abs_name)
    env = metadata.environ
    if env == 'main_file':
        # never used, the main_file is compiled with the latex_main() function
        logger.error("should never reach this line")
        fake_texfile.write(open(os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex')).read())
        fake_texfile.close()
    else:
        #
        ltclsch = metadata.get('latex_documentclass_choice')
        ltclsch = ltclsch[0] if ltclsch else 'auto'
        ltcls = options.get('documentclass')
        if ltclsch == 'auto':
            if env in ('section','E_document'):
                ltclsch = 'main'
            else:
                ltclsch = 'standalone'
        if ltclsch == 'main' and not ltcls:
            logger.warning('When LaTeXing uuid %r, could not use latex_documentclass_choice = "main"', uuid)
            ltclsch = 'standalone'
        if ltclsch == 'main':
            latextemplate = preview_template
            D['documentclass'] = ltcls
            ltclsopt = options.get('documentclassoptions')
            D['documentclass_options'] = ltclsopt
        elif ltclsch == 'standalone':
            latextemplate = standalone_template
        elif ltclsch in ('article','book'):
            latextemplate = preview_template
            D['documentclass'] = ltclsch
        else:
            raise RuntimeError("unimplemented  latex_documentclass_choice = %r",ltclsch)
        fake_texfile.write(latextemplate % D)
        fake_texfile.close()
    rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, options)
    ##
    # rewrite log to replace temporary file name with final file name
    try:
        a = open(save_abs_name+'.log').read()
        b = a.replace(fake_name,save_name)
        open(save_abs_name+'.log','w').write(b)
    except Exception as e:
        logger.warning(e)
    ## create html
    logger.debug('create html for %r',save_abs_name)
    main_file = open(fake_abs_name+'.tex', 'w')
    D['url_UUID'] = ColDoc.config.ColDoc_url_placeholder
    main_file.write(plastex_template % D)
    main_file.close()
    rh = plastex_engine(blobs_dir, fake_name, save_name, environ, options)
    # TODO there is a fundamental mistake here. This function may be called to
    # update the PDF/HTML view of only one language. This timestamp
    # does not record which language was updated. We should have different timestamps
    # for different languages.
    metadata.latex_time_update()
    metadata.save()
    return rh, rp

def  latex_main(blobs_dir, uuid='001', lang=None, options = {}):
    "latex the main document, as the authors intended it ; save all results in UUID dir, as main.* "
    #
    assert isinstance(blobs_dir, (str, pathlib.Path)), blobs_dir
    assert os.path.isdir(blobs_dir)
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                              blobs_dir = blobs_dir,
                                              coldoc = options.get('coldoc'),
                                              metadata_class= options['metadata_class'])
    environ = metadata.environ
    #
    if lang is not None:
        langs=[lang]
    else:
        langs=metadata.get('lang')
    #
    ret = True
    retcodes = {}
    for lang in  langs:
        #
        _lang = ('_'+lang) if (isinstance(lang,str) and lang) else ''
        lang_ = (':'+lang) if (isinstance(lang,str) and lang) else ''
        #
        uuid_dir = ColDoc.utils.uuid_to_dir(uuid, blobs_dir=blobs_dir)
        # note that extensions are missing
        save_name = os.path.join(uuid_dir, 'main' + _lang)
        save_abs_name = os.path.join(blobs_dir, save_name)
        fake_name = 'fakemain' + _lang
        fake_abs_name = os.path.join(blobs_dir, fake_name)
        #
        a = os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex')
        f = open(a).read()
        # FIXME should check in preamble
        try:
            j = f.index(r'\begin{document}')
        except:
            logger.exception(r" cannot locate '\begin{document}' ") 
        else:
            if not r'\usepackage{ColDocUUID}' in f:
                f = f[:j] + r'\usepackage{ColDocUUID}' + f[j:]
                logger.info(r" adding \usepackage{ColDocUUID}")
            f_pdf = f[:j] + (r'\def\uuidbaseurl{%s}'%(options['url_UUID'],)) + f[j:]
            f_html = f[:j] + (r'\def\uuidbaseurl{%s}'%(ColDoc.config.ColDoc_url_placeholder,)) + f[j:]
        #
        open(fake_abs_name+'.tex','w').write(f_pdf)
        rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, options)
        retcodes['latex'+lang_] = rp
        try:
            ColDoc.utils.os_rel_symlink(save_name+'.pdf','main'+_lang+'.pdf',
                                        blobs_dir, False, True)
        except:
            logger.exception('while symlinking')
        open(fake_abs_name+'.tex','w').write(f_html)
        rh = plastex_engine(blobs_dir, fake_name, save_name, environ, options,
                            levels = True, tok = True, strip_head = False)
        retcodes['plastex'+lang_] = rh
        try:
            ColDoc.utils.os_rel_symlink(save_name+'_html','main'+_lang+'_html',
                                        blobs_dir, True, True)
        except:
            logger.exception('while symlinking')
        #
        for e in ('.aux','.bbl','_plastex.paux'):
            # keep a copy of the aux file
            # TODO should encode by language
            a,b = osjoin(blobs_dir,save_name+e), osjoin(blobs_dir,'main'+e)
            if os.path.isfile(a):
                logger.info('Copy %r to %r',a,b)
                shutil.copy(a,b)
        #
        ret = ret and rh and rp
    coldoc = options.get('coldoc')
    if coldoc is not None:
        coldoc.latex_time_update()
        if ret:
            coldoc.latex_return_codes = ''
        else:
            coldoc.latex_return_codes = json.dumps(retcodes)
        coldoc.save()
    return ret


def plastex_engine(blobs_dir, fake_name, save_name, environ, options,
                   levels = False, tok = False, strip_head = True):
    " compiles the `fake_name` latex, and generates the `save_name` result ; note that extensions are missing "
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    #
    fake_support=[]
    for es,ed in ColDoc.config.ColDoc_plastex_fakemain_reuse_extensions:
        a = osjoin(blobs_dir,'main'+es)
        if os.path.exists(a):
            logger.info("Re-using %r as %r",a,fake_abs_name+ed)
            shutil.copy2(a,fake_abs_name+ed)
            fake_support.append((a,fake_abs_name+ed))
        elif os.path.exists(save_abs_name+es):
            logger.info("Re-using %r as %r",save_abs_name+es,fake_abs_name+ed)
            shutil.copy(save_abs_name+es,fake_abs_name+ed)
            fake_support.append((save_abs_name+es,fake_abs_name+ed))
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
    argv = ['-d',save_name+'_html',"--renderer=HTML5", ]
    if not levels :
        argv += [ '--split-level','0']
    if tok is False or (environ[:2] == 'E_' and tok == 'auto'):
        argv.append( '--no-display-toc' )
    # do not use ['--paux-dirs',save_name+'_paux'] until we understand what it does
    argv += ['--log',F]
    ret = ColDoc.utils.plastex_invoke(cwd_ =  blobs_dir ,
                         stdout_  = open(osjoin(blobs_dir,save_name+'_plastex.stdout'),'w'),
                         argv_ = argv )
    extensions = '.log','.paux','.tex','.bbl'
    if ret :
        logger.warning('Failed: cd %r ; plastex %s',blobs_dir,' '.join(argv))
    for e in extensions:
        if os.path.exists(save_abs_name+'_plastex'+e):
            os.rename(save_abs_name+'_plastex'+e,save_abs_name+'_plastex'+e+'~')
        if os.path.exists(fake_abs_name+e):
            s,d = fake_abs_name+e,save_abs_name+'_plastex'+e
            os.rename(s,d)
            if ret: logger.warning(' rename %r to %r',s,d)
    if os.path.isfile(osjoin(blobs_dir, save_name+'_html','index.html')):
        logger.info('created html version of %r ',save_abs_name)
    else:
        logger.warning('no "index.html" in %r',save_name+'_html')
        return False
    #
    if strip_head:
        for f in os.listdir(osjoin(blobs_dir, save_name+'_html')):
            f = osjoin(blobs_dir, save_name+'_html', f)
            if f[-5:]=='.html':
                logger.info('stripping <head> of %r ',f)
                os.rename(f,f+'~~')
                L=open(f+'~~').readlines()
                try:
                    ns, ne = None,None
                    for n,s in enumerate(L):
                        s = s.strip()
                        if s == '<body>': ns =  n
                        if s == '</body>': ne =  n
                    assert ns,ne
                    L = L[ns+1:ne]
                    F = open(f,'w')
                    for l in L:
                        if l[:7] != '<script':
                            F.write(l)
                except:
                    logger.exception('ARGH')
    return ret == 0


def pdflatex_engine(blobs_dir, fake_name, save_name, environ, options, repeat = False):
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    # 'main.aux' and 'main.bbl' are saved latex_main()
    for e in ColDoc.config.ColDoc_pdflatex_fakemain_reuse_extensions:
        a = os.path.join(blobs_dir,'main'+e)
        if os.path.exists(save_abs_name+e):
            logger.info("Re-using %r for %r",save_abs_name+e,fake_abs_name+e)
            shutil.copy2(save_abs_name+e, fake_abs_name+e)
        elif os.path.exists(a):
            logger.info("Re-using %r for %r (hoping for the best)",a,fake_abs_name+e)
            shutil.copy2(a,fake_abs_name+e)
        else:
            logger.info("No %r file for this job",e)
    #
    extensions = ColDoc.config.ColDoc_pdflatex_fakemain_preserve_extensions
    #
    for e in extensions:
        if e not in ('.tex','.aux','.bbl') and os.path.exists(fake_abs_name+e):
            logger.warning('Overwriting: %r',fake_abs_name+e)
    #
    engine = options.get('latex_engine','pdflatex')
    logger.debug('Using engine %r',engine)
    args = [engine,'-file-line-error','-interaction','batchmode',
            '-recorder','-no-shell-escape','-no-parse-first-line',
            ##TODO may use -output-directory directory
            ## TODO TEST THIS
            ##( r"\def\uuidbaseurl{%s}" % (options['url_UUID'],)),   r"\input",
            ## TODO for luatex may add --nosocket --safer
            fake_name+'.tex']
    #
    p = subprocess.Popen(args,cwd=blobs_dir,stdin=open(os.devnull),
                         stdout=open(os.devnull,'w'),stderr=subprocess.STDOUT)
    r=p.wait()
    logger.debug('Engine result %r',r)
    #
    if environ in ( 'main_file', 'E_document') and \
         os.path.isfile(fake_abs_name+'.aux') and \
         '\\bibdata' in open(fake_abs_name+'.aux').read():
        logger.debug('Running BiBTeX')
        p = subprocess.Popen(['bibtex',fake_name],
                             cwd=blobs_dir,stdin=open(os.devnull),
                             stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
        a = p.stdout.read()
        if p.wait() != 0:
            logger.warning('bibtex fails, see %r'%(save_abs_name+'.blg',))
            logger.warning('bibtex output: %r',a)
    #
    if r == 0 and repeat:
        logger.debug('Rerunning engine %r',engine)
        p = subprocess.Popen(args,cwd=blobs_dir,stdin=open(os.devnull),
                             stdout=open(os.devnull,'w'),stderr=subprocess.STDOUT)
        r = p.wait()
        logger.debug('Engine result %r',r)
    #
    res = r == 0
    if not res:
        logger.warning('%r fails, see %r'%(engine,save_abs_name+'.log'))
    #
    for e in extensions:
        if os.path.exists(save_abs_name+e):
            os.rename(save_abs_name+e,save_abs_name+e+'~')
        if os.path.exists(fake_abs_name+e):
            if e == '.pdf':
                siz=os.path.getsize(fake_abs_name+e)
                if siz :
                    logger.info("Created pdf %r size %d"%(save_abs_name+e,siz))
                else:
                    logger.warning("Created empty pdf %r "%(save_abs_name+e,))
            a,b=fake_abs_name+e,save_abs_name+e
            logger.debug('Rename %r to %r',a,b)
            os.rename(a,b)
        else:
            if e not in ( '.pdf', '.aux' ) :
                logger.debug("Missing :%r"%(fake_abs_name+e,))
            else:
                logger.warning("Missing :%r"%(fake_abs_name+e,))
                if e=='.pdf': res=False
    return res


def latex_tree(blobs_dir, uuid=None, lang=None, warn=False, options={}):
    " latex the whole tree, starting from `uuid` "
    warn = logging.WARNING if warn else logging.DEBUG
    if uuid is None:
        logger.warning('Assuming root_uuid = 001')
        uuid = '001'
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir,
                                                   coldoc = options.get('coldoc'),
                                                   metadata_class=options['metadata_class'])
    #
    ret = True
    if metadata.environ in environments_we_wont_latex and warn:
        logger.log(warn, 'Cannot `pdflatex` environ %r , UUID = %r'%(metadata.environ, uuid,))
    else:
        r = latex_uuid(blobs_dir, uuid=uuid, metadata=metadata, lang=lang, warn=warn, options=options)
        ret = ret and r
    for u in metadata.get('child_uuid'):
        logger.debug('moving down from node %r to node %r',uuid,u)
        r = latex_tree(blobs_dir, uuid=u, lang=lang, warn=warn, options=options)
        ret = ret and r
    return ret



def prepare_options_for_latex(coldoc_dir, blobs_dir, metadata_class, coldoc=None): 
    a = osjoin(coldoc_dir, 'coldoc.json')
    options = {}
    if os.path.isfile( a ):
        coldoc_args = json.load(open(a))
        options = coldoc_args['fields']
        #
        coldoc_root_uuid = options.get('root_uuid')
        if isinstance(coldoc_root_uuid,int):
            coldoc_root_uuid = ColDoc.utils.int_to_uuid(coldoc_root_uuid)
        options['root_uuid'] = coldoc_root_uuid
        #
        root_filename, root_uuid, root_metadata, root_lang, root_ext =\
            ColDoc.utils.choose_blob(uuid=coldoc_root_uuid, blobs_dir=blobs_dir, metadata_class=metadata_class, coldoc=coldoc)
        for a in ('documentclass', 'documentclassoptions'):
            b = root_metadata.get(a)
            if b:
                options[a] = b[0]
                logger.debug('In root uuid  %r = %r',a,b)
            else:
                logger.warning('In root uuid no value for %r',a)
        #
        logger.debug('From %r options %r',a,options)
    else:
        logger.error('No %r',a)
    #
    a = osjoin(blobs_dir, '.blob_inator-args.json')
    if os.path.isfile( a ):
        blob_inator_args = json.load(open(a))
        assert isinstance(blob_inator_args,dict)
        options.update(blob_inator_args)
        logger.debug('From %r options %r',a,options)
    else:
        logger.debug('No %r',a)
    return options



def prepare_parser():
    # parse arguments
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser = argparse.ArgumentParser(description='Compile coldoc material, using `latex` and `plastex` ',
                                     epilog=cmd_help,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--uuid',help='UUID to work on/start from')
    parser.add_argument('command', help='specific command',nargs='+')
    return parser

def main(argv):
    parser = prepare_parser()
    parser.add_argument('--blobs-dir',type=str,\
                        help='directory where the blob_ized output is saved',
                        required=True)
    parser.add_argument('--url-UUID',type=str,\
                        help='URL of the website that will show the UUIDs, used by my \\uuid macro in PDF',
                        required=True)
    args = parser.parse_args(argv[1:])
    #
    blobs_dir = args.blobs_dir
    assert os.path.isdir(blobs_dir), blobs_dir
    #
    args.coldoc_dir = coldoc_dir = os.path.dirname(os.path.dirname(blobs_dir))
    from ColDoc.utils import FMetadata
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, FMetadata)
    options['url_UUID'] = args.url_UUID
    #
    def foobar(*v, **k):
        " helper factory"
        return ColDoc.transform.squash_input_uuid(*v, **k)
    options["squash_helper"] = foobar
    options['metadata_class'] = ColDoc.utils.FMetadata
    return main_by_args(args,options)


def main_by_args(args,options):
    argv = args.command
    blobs_dir = args.blobs_dir
    coldoc_dir = args.coldoc_dir
    logger.setLevel(logging.WARNING)
    if args.verbose > 1 :
        logger.setLevel(logging.DEBUG)
    elif args.verbose > 0 :
        logger.setLevel(logging.INFO)
    #
    if args.uuid is not None:
        UUID = args.uuid
    elif 'root_uuid' in options:
        UUID = options['root_uuid']
    else:
        UUID = '001'
    #
    ret = True
    if argv[0] == 'blob':
        lang = None
        if len(argv)>2:
            lang = argv[2]
        ret = latex_uuid(blobs_dir,UUID,lang=lang, options=options)
    elif argv[0] == 'tree':
        ret = latex_tree(blobs_dir,UUID, options=options)
    elif argv[0] == 'main':
        ret = latex_main(blobs_dir, uuid=UUID, options=options)
    elif argv[0] == 'anon':
        n, anon_dir = ColDoc.utils.prepare_anon_tree(coldoc_dir, uuid=None, lang=None, warn=False,
                                                  metadata_class=ColDoc.utils.FMetadata)
        if anon_dir is not None:
            ret = latex_main(anon_dir, uuid=UUID, options=options)
        else:
            ret = False
    elif argv[0] == 'all':
        ret = latex_main(blobs_dir, uuid=UUID, options=options)
        ret &= latex_tree(blobs_dir,UUID, options=options)
        n, anon_dir = ColDoc.utils.prepare_anon_tree(coldoc_dir, uuid=None, lang=None, warn=False, 
                                                 metadata_class=ColDoc.utils.FMetadata)
        if anon_dir is not None:
            assert isinstance(anon_dir, (str, pathlib.Path)), anon_dir
            ret &= latex_main(anon_dir, uuid=UUID, options=options)
        else:
            ret = False
    else:
        sys.stderr.write('Unknown command, see --help')
        return False
    return ret


if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

