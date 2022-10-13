#!/usr/bin/env python3

__all__ = ('main_by_args','latex_main','latex_uuid','latex_tree')

def _(s):
    "mark translatable strings; no attempt is made to translate them, since most code here is a library"
    return s


cmd_help=_("""
Command help:

    blob
       compile the blob(s) with --uuid=UUID,
    
    tree
       compile all the blobs starting from --uuid=UUID

    main_public
       compile the whole document, for the general public

    main_private
       compile the whole document, including protected material, visible to the editors

    all
       all of the above
""")

import os, sys, shutil, subprocess, json, argparse, pathlib, tempfile, hashlib, pickle, base64, re, json, dbm

if sys.version_info >= (3,9):
    from os import waitstatus_to_exitcode
else:
    def waitstatus_to_exitcode(status):
        return os.WEXITSTATUS(status) if os.WIFEXITED(status) else \
               ( - os.WTERMSIG(status) if os.WIFSIGNALED(status) else None)

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

####

try:
    import unicode2latex
except ImportError:
    logger.warning('Please install `unicode2latex` ')
    unicode2latex = None

############## ColDoc stuff

re_setcounter = re.compile(r'\\setcounter\s*{\s*([a-zA-Z@]*)\s*}\s*{\s*([0-9-]*)\s*}')

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

environments_we_wont_latex = ColDoc.config.ColDoc_environments_we_wont_latex

standalone_template=r"""\documentclass[varwidth=%(width)s]{standalone}
%(coldoc_api)s
%(language_conditionals)s
%(latex_macros)s
\def\uuidbaseurl{%(url_UUID)s}
\input{%(preamble)s}
\usepackage{ColDocUUID}
\begin{document}
%(checkpoint)s
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""

preview_template=r"""\documentclass %(documentclass_options)s {%(documentclass)s}
%(coldoc_api)s
%(language_conditionals)s
%(latex_macros)s
\def\uuidbaseurl{%(url_UUID)s}
\input{%(preamble)s}
\usepackage{hyperref}
\usepackage{ColDocUUID}
\begin{document}
%(checkpoint)s
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""
## TODO investigate, this generates an empty PDF
##\setlength\PreviewBorder{5pt}
##%\usepackage[active]{preview}

plastex_template=r"""\documentclass{article}
%(coldoc_api)s
%(language_conditionals)s
%(latex_macros)s
\def\uuidbaseurl{%(url_UUID)s}
\input{%(preamble)s}
\usepackage{hyperref}
\usepackage{ColDocUUID}
\begin{document}
%(checkpoint)s
%(begin)s
\input{%(input)s}
%(end)s
\end{document}
"""

def lang_conditionals(thelang, langs = None, metadata = None):
    if langs is None:
        e = ('mul','zxx','und')
        langs = set()
        langs.update(l for l in metadata.get_languages() if l not in e)
        langs.update(l for l in metadata.coldoc.get_languages() if l not in e)
    return [(r'\newif\if{I}{L}\{I}{L}{V}'.format(I=ColDoc.config.ColDoc_language_conditional_infix,\
                                                 V='true' if a == thelang else 'false',\
                                                 L=a)) \
            for a in langs]


@ColDoc.utils.log_debug
def latex_uuid(blobs_dir, uuid=None, lang=None, metadata=None, warn=True, options = {}):
    " `latex` the blob identified `uuid` or `metadata`; if `lang` is None, `latex` all languages ; return a dict of booleans to report failure for each language "
    log_level = logging.WARNING if warn else logging.DEBUG
    assert uuid is not None or metadata is not None
    if metadata is None:
        uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                blobs_dir = blobs_dir,
                                coldoc = options.get('coldoc'),
                                metadata_class= options['metadata_class'])
    else:
        uuid_ = metadata.uuid
        uuid_dir = None
    assert uuid is None or uuid == uuid_
    uuid = uuid_
    #
    if metadata.environ == 'main_file':
        logger.log(log_level, 'Do not need to `pdflatex` the main_file')
        return {l:True for l in metadata.get_languages()}
    #
    if lang is not None:
        langs = [lang]
    else:
        langs = metadata.get_languages()
    if 'mul' in langs:
        langs = metadata.coldoc.get_languages()
    if not langs:
        logger.debug('No languages for blob %r in blobs_dir %r',uuid,blobs_dir)
        return True
    #
    res = {}
    langpids = []
    for l in langs:
        if sys.platform == 'linux' and len(langs)>1:
            other_pid_ = os.fork()
            if other_pid_ == 0:
                rh, rp = latex_blob(blobs_dir, metadata=metadata, lang=l,
                                    uuid_dir=uuid_dir, options = options, forked=True)
                rh = 0 if rh else 4
                rp = 0 if rp else 8
                os._exit(rh + rp)
            else:
                logger.debug('fork %r', other_pid_)
                langpids.append((l, other_pid_))
        else:
            rh, rp = latex_blob(blobs_dir, metadata=metadata, lang=l,
                                uuid_dir=uuid_dir, options = options)
            res[l] = rh and rp
    #
    for ll, other_pid_ in langpids:
        logger.debug('wait %r', other_pid_)
        pid_, exitstatus_ = os.waitpid(other_pid_, 0)
        if pid_ != other_pid_:
            logger.error('internal error lnkanla19')
        exitstatus_ = waitstatus_to_exitcode(exitstatus_)
        if exitstatus_ not in (0,4,8,12):
            logger.error('internal error exitstatus_ %r', exitstatus_)
        rh = (exitstatus_ & 4 ) == 0
        rp = (exitstatus_ & 8 ) == 0
        _update_metadata(metadata, ll, rh, rp)
        res[ll] = (exitstatus_ == 0)
    #
    if lang is None:
        # update only if all languages were recomputed
        metadata.latex_time_update()
    metadata.save()
    return res

@ColDoc.utils.log_debug
def  latex_blob(blobs_dir, metadata, lang, uuid_dir=None, options = {}, squash = True, forked=False):
    """ `latex` the blob identified by the `metadata`, for the given language `lang`.
    ( `uuid` and `uuid_dir` are courtesy , to avoid recomputing )
    Optionally squashes all sublevels, replacing with \\uuidplaceholder """
    #
    environ = metadata.environ
    #
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
    ####
    # find a preamble
    preambles = []
    preamble_opt = options.get('preamble')
    if preamble_opt is not None:
        if '{lang}' in preamble_opt:
            preamble_opt = preamble_opt.format(lang=lang)
        preambles.append((preamble_opt, 'option'))
    preambles.append(('preamble' + _lang + '.tex','lang'))
    for l in metadata.coldoc.get_languages():
        preambles.append(('preamble_' + l + '.tex','coldoc langs'))
    preamble = None
    for p,o in preambles:
        if os.path.isfile(osjoin(blobs_dir, p)):
            preamble = p
            break
        else:
            b = 'Cannot find preamble from %s: %s/%s' % (o, blobs_dir, p)
            with open(save_abs_name+'.log','w') as f_:
                f_.write(uuid_dir + ':0:' + b + '\n')
            logger.warning(b)
    if preamble is None:
        retcodes = ColDoc.utils.json_to_dict(metadata.latex_return_codes)
        j = (':'+lang) if (isinstance(lang,str) and lang) else ''
        ColDoc.utils.dict_save_or_del( retcodes, 'latex'+j, False)
        metadata.latex_return_codes = ColDoc.utils.dict_to_json(retcodes)
        metadata.save()
        return False, False
    #
    D = {'uuiddir':uuid_dir, 'lang':lang, 'uuid':uuid,
         '_lang':_lang,
         'width':'4in',
         'begin':'','end':'',
         'url_UUID' : options['url_UUID'],
         'latex_macros' : options.get('latex_macros',metadata.coldoc.latex_macros_uuid),
         'coldoc_api' : ColDoc.config.ColDoc_api_version_macro,
         'language_conditionals' : '\n'.join(lang_conditionals(lang, metadata = metadata)),
         'preamble' : preamble,
         }
    #
    a = os.path.join(blobs_dir,uuid_dir,'blob'+_lang+'.tex.checkpoint')
    if os.path.exists(a):
        if environ.startswith('E_'):
            ckp = ''
            for l in open(a):
                c = None
                for c,n in re_setcounter.findall(l):
                    n = int(n)
                    if '@' not in c and c not in ColDoc.config.ColDoc_dont_decrement_counters and n>0:
                        n -= 1
                    ckp += '\\setcounter{%s}{%d}\n' % (c,n)
                # now this just copies "relax"
                if c is None:
                    ckp += l
            D['checkpoint'] = ckp
        else:
            D['checkpoint'] = open(a).read()
    else:
        D['checkpoint'] = ''
    #
    b = os.path.join(uuid_dir,'blob'+_lang+'.tex')
    s = os.path.join(uuid_dir,'squash'+_lang+'.tex')
    # 'compile' the bibliography by compiling the `.bib` file
    if environ in  ('bibliography', 'E_thebibliography'):
        b = None
        b_bbls = [ 'main'+_lang+'.bbl' ] + [ ('main_'+l+'.bbl') for l in metadata.coldoc.get_languages() ]
        for a in b_bbls:
            if os.path.isfile(osjoin(blobs_dir, a)):
                b = a
                break
        if b is None:
            logger.warning('when compiling UUID %r , no file %r is available', uuid, b_bbls)
            squash = False
            b_temp = tempfile.NamedTemporaryFile(dir=blobs_dir,suffix='.tex')
            b = b_temp.name
            b_temp.write(b'Please compile the main private file and then recompile this UUID')
            b_temp.flush()
    # 'compile' the preamble files by compiling an empty file
    elif environ in environments_we_wont_latex:
        b_temp = tempfile.NamedTemporaryFile(dir=blobs_dir,suffix='.tex')
        b = b_temp.name
        b_temp.write(b'Placeholder')
        b_temp.flush()
        squash = False
    #
    if squash:
        helper = options.get('squash_helper')(blobs_dir=blobs_dir, metadata=metadata, lang=lang, options=options)
        ColDoc.transform.squash_latex(open(osjoin(blobs_dir,b)), open(osjoin(blobs_dir,s),'w'), options,
                                      helper = helper)
        D['input'] = s
    else:
        D['input'] = b
    #
    if environ[:2] == 'E_' and environ not in ( 'E_document', 'E_thebibliography', ):
        env = environ[2:]
        D['begin'] = r'\begin{'+env+'}'
        D['end'] = r'\end{'+env+'}'
        if 'split_list' in options and env in options['split_list']:
            D['begin'] += r'\item'
    ##
    ## create pdf
    logger.debug('create pdf for %r',save_abs_name)
    if environ == 'main_file':
        # never used, the main_file is compiled with the latex_main() function
        logger.error("should never reach this line")
        assert False
        #fake_texfile.write(open(os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex')).read())
        #fake_texfile.close()
    else:
        #
        ltclsch = metadata.get('latex_documentclass_choice')
        ltclsch = ltclsch[0] if ltclsch else 'auto'
        ltcls = options.get('documentclass')
        if ltclsch == 'auto':
            if environ in  ColDoc.config.ColDoc_environments_sectioning or  environ == 'E_document':
                ltclsch = 'main'
            else:
                ltclsch = 'standalone'
        if ltclsch == 'main' and not ltcls:
            logger.warning('When LaTeXing uuid %r, could not use latex_documentclass_choice = "main"', uuid)
            ltclsch = 'standalone'
        if ltclsch == 'main':
            latextemplate = preview_template
            D['documentclass'] = ltcls
        elif ltclsch == 'standalone':
            latextemplate = standalone_template
        elif ltclsch in ('article','book'):
            latextemplate = preview_template
            D['documentclass'] = ltclsch
        else:
            raise RuntimeError("unimplemented  latex_documentclass_choice = %r",ltclsch)
        # from metadata or from coldoc
        ltclsopt = metadata.get('documentclassoptions')
        if ltclsopt:
            ltclsopt = ltclsopt[0]
        else:
            ltclsopt = options.get('documentclassoptions')
        ltclsopt = ColDoc.utils.parenthesizes(ltclsopt, '[]')
        D['documentclass_options'] = ltclsopt
        #
    fake_texfile = tempfile.NamedTemporaryFile(prefix='fakelatex' + _lang + '_' + uuid + '_',
                                               suffix='.tex', dir = blobs_dir , mode='w+', delete=False)
    fake_abs_name = fake_texfile.name[:-4]
    fake_name = os.path.basename(fake_abs_name)
    fake_texfile.write(latextemplate % D)
    fake_texfile.close()
    #
    other_pid_ = rp = None
    if sys.platform == 'linux':
        # forking
        other_pid_ = os.fork()
        if other_pid_ == 0:
            rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, lang, options)
            os._exit(0 if rp else 13)
        else:
            logger.debug('Forked pdflatex_engine to pid %r', other_pid_)
    else:
        logger.warning('FIXME no forking in your platform')
        rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, lang, options)
    ##
    ## create html
    logger.debug('create html for %r',save_abs_name)
    fake_texfile2 = tempfile.NamedTemporaryFile(prefix='fakelatex' + _lang + '_' + uuid + '_',
                                               suffix='.tex', dir = blobs_dir , mode='w+', delete=False)
    fake_abs_name2 = fake_texfile2.name[:-4]
    fake_name2 = os.path.basename(fake_abs_name2)
    main_file = open(fake_abs_name2+'.tex', 'w')
    D['url_UUID'] = ColDoc.config.ColDoc_url_placeholder
    main_file.write(plastex_template % D)
    main_file.close()
    rh = plastex_engine(blobs_dir, fake_name2, save_name, environ, uuid, lang, options)
    # paux is quite large and it will not be used after this line
    if os.path.isfile(save_abs_name+'_plastex.paux'):
        os.unlink(save_abs_name+'_plastex.paux')
    #
    # get child result
    if other_pid_ is not None:
        pid_, exitstatus_ = os.waitpid(other_pid_, 0)
        if pid_ != other_pid_:
            logger.error('internal error kjnbfi20a')
        exitstatus_ = waitstatus_to_exitcode(exitstatus_)
        rp = (exitstatus_ == 0)
    #
    # rewrite pdflatex log to replace temporary file name with final file name
    for ext in '.log','.fls':
        try:
            a = open(save_abs_name+ext).read()
            b = a.replace(fake_name,save_name)
            with open(save_abs_name+ext,'w') as f_:
                f_.write(b)
        except Exception as e:
            logger.warning(e)
    #
    if environ in environments_we_wont_latex:
        try:
            os.unlink(save_abs_name + '.pdf')
            shutil.rmtree(save_abs_name + '_html')
        except:
            logger.exception('While removing compiled placeholders')
    #
    if not forked:
        # when forked, cannot update metadata here, it would clash with other processes
        _update_metadata(metadata, lang, rh, rp)
    return rh, rp

def _update_metadata(metadata, lang, rh, rp):
    # TODO there is a fundamental mistake here. This function may be called to
    # update the PDF/HTML view of only one language. This timestamp
    # does not record which language was updated. We should have different timestamps
    # for different languages.
    if len(metadata.get('lang')) == 1:
        metadata.latex_time_update()
    #
    retcodes = ColDoc.utils.json_to_dict(metadata.latex_return_codes)
    j = (':'+lang) if (isinstance(lang,str) and lang) else ''
    ColDoc.utils.dict_save_or_del( retcodes, 'latex'+j, rp)
    ColDoc.utils.dict_save_or_del( retcodes, 'plastex'+j, rh)
    metadata.latex_return_codes = ColDoc.utils.dict_to_json(retcodes)
    #
    metadata.save()

@ColDoc.utils.log_debug
def  latex_anon(coldoc_dir, uuid='001', lang=None, options = {}, access='public', verbose_name=None, email_to=None):
    #
    assert access=='public'
    #
    if isinstance(options, (str,bytes) ):
        # base64 accepts both bytes and str
        options = pickle.loads(base64.b64decode(options))
    #
    metadata_class = options.get('metadata_class')
    assert coldoc_dir == options.get('coldoc_dir',coldoc_dir)
    coldoc = options.get('coldoc')
    warn = options.get('warn')
    #
    n, anon_dir = ColDoc.utils.prepare_anon_tree(coldoc_dir, uuid=uuid, lang=lang,
                                                 metadata_class=metadata_class, coldoc=coldoc)
    if anon_dir is not None:
        assert isinstance(anon_dir, (str, pathlib.Path)), anon_dir
        return latex_main(anon_dir, uuid=uuid, lang=lang, options = options, access='public', verbose_name=verbose_name, email_to=email_to)
    else:
        return False


@ColDoc.utils.log_debug
def  latex_main(blobs_dir, uuid='001', lang=None, options = {}, access=None, verbose_name=None, email_to=None):
    "latex the main document, as the authors intended it ; save all results in UUID dir, as main.* "
    #
    assert access in ('public','private')
    assert isinstance(blobs_dir, (str, pathlib.Path)), blobs_dir
    assert os.path.isdir(blobs_dir)
    #
    if isinstance(options, (str,bytes) ):
        # base64 accepts both bytes and str
        options = pickle.loads(base64.b64decode(options))
    #
    metadata_class = options.get('metadata_class')
    coldoc_dir = options.get('coldoc_dir')
    coldoc = options.get('coldoc')
    #
    if coldoc_dir is not None:
        options = prepare_options_for_latex(coldoc_dir, blobs_dir, metadata_class, coldoc, options)
    #
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                              blobs_dir = blobs_dir,
                                              coldoc = coldoc,
                                              metadata_class = metadata_class)
    environ = metadata.environ
    #
    if access =='public':
        options['plastex_theme'] = 'blue'
        latex_macros = metadata.coldoc.latex_macros_public
    else:
        options['plastex_theme'] = 'green'
        latex_macros = metadata.coldoc.latex_macros_private
    #
    if lang is not None:
        langs = [lang]
    else:
        langs = metadata.get_languages()
    if 'mul' in langs:
        langs = metadata.coldoc.get_languages()
    #
    ret = True
    coldoc = options.get('coldoc')
    if coldoc is not None:
        retcodes = ColDoc.utils.json_to_dict(coldoc.latex_return_codes)
    #
    for lang in  langs:
        #
        _lang = ('_'+lang) if (isinstance(lang,str) and lang) else ''
        lang_ = (':'+lang) if (isinstance(lang,str) and lang) else ''
        #
        uuid_dir = ColDoc.utils.uuid_to_dir(uuid, blobs_dir=blobs_dir)
        # note that extensions are missing
        save_name = os.path.join(uuid_dir, 'main' + _lang)
        save_abs_name = os.path.join(blobs_dir, save_name)
        #
        a = os.path.join(blobs_dir, uuid_dir, 'blob'+_lang+'.tex')
        prologue, preamble, body, epilogue = ColDoc.utils.split_blob(open(a))
        if not(preamble):
            logger.warning(r" cannot locate '\begin{document}' ") 
        if True:
            conditionals = lang_conditionals(lang, metadata = metadata)
            preamble = [ColDoc.config.ColDoc_api_version_macro, latex_macros] + conditionals + preamble
            import re
            r = re.compile(r'\\usepackage{ColDocUUID}')
            if not any(r.match(a) for a in preamble):
                preamble += ['\\usepackage{ColDocUUID}\n']
                logger.debug(r" adding \usepackage{ColDocUUID}")
            a = (r'\def\uuidbaseurl{%s}'%(options['url_UUID'],)+'\n')
            f_pdf = ''.join(prologue + preamble + [a] + body + epilogue)
            a = (r'\def\uuidbaseurl{%s}'%(ColDoc.config.ColDoc_url_placeholder,)+'\n')
            f_html = ''.join(prologue + preamble + [a] + body + epilogue)
        #
        fake_texfile = tempfile.NamedTemporaryFile(prefix='fakelatex' + _lang +'_',
                                                    suffix='.tex', dir = blobs_dir , mode='w+', delete=False)
        fake_abs_name = fake_texfile.name[:-4]
        fake_name = os.path.basename(fake_abs_name)
        with open(fake_abs_name+'.tex','w') as f_:
            f_.write(f_pdf)
        #
        other_pid_ = rp = None
        if sys.platform == 'linux':
            # forking
            other_pid_ = os.fork()
            if other_pid_ == 0:
                rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, lang, options)
                os._exit(0 if rp else 13)
            else:
                logger.debug('Forked pdflatex_engine to pid %r', other_pid_)
        else:
            logger.warning('FIXME no forking in your platform')
            rp = pdflatex_engine(blobs_dir, fake_name, save_name, environ, lang, options)
        #
        # plastex
        fake_texfile2 = tempfile.NamedTemporaryFile(prefix='fakelatex' + _lang + '_',
                                               suffix='.tex', dir = blobs_dir , mode='w+', delete=False)
        fake_abs_name2 = fake_texfile2.name[:-4]
        fake_name2 = os.path.basename(fake_abs_name2)
        with open(fake_abs_name2+'.tex','w') as f_:
            f_.write(f_html)
        rh = plastex_engine(blobs_dir, fake_name2, save_name, environ, uuid, lang, options,
                            levels = True, tok = True, strip_head = False)
        parse_plastex_html(blobs_dir, osjoin(blobs_dir, save_name+'_html'), save_abs_name+'_plastex.paux')
        # paux is quite large and it will not be used after this line
        try:
            os.unlink(save_abs_name+'_plastex.paux')
        except:
            logger.exception('while unlinking '+save_abs_name+'_plastex.paux')
        ColDoc.utils.dict_save_or_del(retcodes, 'plastex'+lang_+':'+access, rh)
        try:
            ColDoc.utils.os_rel_symlink(save_name+'_html','main'+_lang+'_html',
                                        blobs_dir, True, True)
        except:
            logger.exception('while symlinking')
        # get pdflatex child result
        if other_pid_ is not None:
            pid_, exitstatus_ = os.waitpid(other_pid_, 0)
            if pid_ != other_pid_:
                logger.error('internal error mnqwkqla9')
            exitstatus_ = waitstatus_to_exitcode(exitstatus_)
            rp = (exitstatus_ == 0)
        #
        ColDoc.utils.dict_save_or_del(retcodes, 'latex'+lang_+':'+access, rp)
        try:
            ColDoc.utils.os_rel_symlink(save_name+'.pdf','main'+_lang+'.pdf',
                                        blobs_dir, False, True)
        except:
            logger.exception('while symlinking')
        #
        for e in ('.aux','.bbl','.ind','_plastex.paux'):
            # keep a copy of the aux file
            a,b = osjoin(blobs_dir,save_name+e), osjoin(blobs_dir,'main'+_lang+e)
            if os.path.isfile(a):
                logger.debug('Copy %r to %r',a,b)
                shutil.copy(a,b)
            else:
                logger.debug('No such file %r , did not copy to %r',a,b)
        #
        ret = ret and rh and rp
    #
    if coldoc is not None:
        if lang is None:
            # update only if all languages were updated
            coldoc.latex_time_update()
        coldoc.latex_return_codes = ColDoc.utils.dict_to_json(retcodes)
        coldoc.save()
    return ret

def parse_plastex_paux(paux):
    if isinstance(paux,str):
        try:
            paux = open(paux,'rb')
        except OSError as e:
            logger.error('Cannot open %r : %r',paux,e)
            return {}
    a = pickle.load(paux)
    a = a['HTML5']
    D = {}
    for n in a:
        try:
            if n.startswith('UUID:'):
                uuid = n[5:]
                url = a[n]['url']
                if '#' in url:
                    S,name = url.split('#')
                    D[uuid] = (S, '#' + name)
                else:
                    D[uuid] = (url, '')
        except:
            logger.exception('vv')
    return D


def parse_plastex_html(blobs_dir, html_dir, paux):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error('Please install BeautifulSoup4: pip3 install BeautifulSoup4')
        return
    D = parse_plastex_paux(paux)
    P = ColDoc.config.ColDoc_url_placeholder
    for S in os.listdir(html_dir):
        if S.endswith('html'):
            name = href = uuid = None
            soup = BeautifulSoup(open(osjoin(html_dir,S)).read(), 'html.parser')
            for link in soup.find_all('a'):
                h = link.get('href')
                n = link.get('name')
                if n:
                    if n.startswith('UUID:'):
                        uuid = n[5:]
                        D[uuid] = (S, n)
                    else:
                        name = n
                if h and h.startswith(P):
                    uuid = h[len(P):]
                    if uuid not in D and name:
                        D[uuid] = (S, '#' + name)
    #pickle.dump(D,open(osjoin(blobs_dir,'.UUID_html_mapping.pickle'),'wb'))
    db = dbm.open(osjoin(blobs_dir,'.UUID_html_mapping.dbm'),'c')
    for k,v in D.items():
        db[k] = json.dumps(v)
    db.close()
    json.dump(D,open(osjoin(blobs_dir,'.UUID_html_mapping.json'),'w'),indent=1)


def get_specific_html_for_UUID(blobs_dir,UUID):
    try:
        db = dbm.open(osjoin(blobs_dir,'.UUID_html_mapping.dbm'))
        return json.loads(db[UUID])
    except KeyError:
        logger.info('Cannot resolve uuid=%r in %r',UUID,blobs_dir)
        return '',''
    except:
        logger.exception('Cannot resolve uuid=%r in %r',UUID,blobs_dir)
        return '',''

def dedup_html(src, options):
    replacements = []
    dedup_root = options.get('dedup_root')
    dedup_url  = options.get('dedup_url')
    if dedup_root is not None:
        coldoc_site_root = options['coldoc_site_root']
        for k in 'js', 'styles', 'symbol-defs.svg' :
            k_ = osjoin(src,k)
            if os.path.exists(k_):
                dedup = ColDoc.utils.replace_with_hash_symlink(coldoc_site_root, src, dedup_root, k)
                if os.path.isfile(k_):
                    replacements.append( (k, dedup_url + '/' + dedup) )
                elif os.path.isdir(k_):
                    for dirpath, dirnames, filenames in os.walk(k_):
                        for f in filenames:
                            a = osjoin(dirpath,f)
                            o = a[(len(src)+1):]
                            r = a[(len(src)+len(k)+2):]
                            replacements.append( ( o, (dedup_url + '/' + dedup + '/' + r) ) )
    return replacements

def convert_html_to_text(IN,OUT, options):
    s = open(IN).read()
    s = ColDoc.utils.html2text(s).lower()
    if unicode2latex:
        extra = options.get('unicode_to_latex')
        s = unicode2latex.uni2tex(s, extra, add_font_modifiers=False, convert_accents=False)
    #s = s.replace('\n\t',' ')
    s = re.sub('\s+',' ',s)
    l = re.split('([.;\]\)}])', s)
    s = ''
    while len(l) > 1:
        s += l[0] + l[1] + '\n'
        l = l[2:]
    if l:
        s += l[0] + '\n'
    with open(OUT,'w') as f_:
        f_.write(s)
    logger.debug('created txt version of %r', IN)

@ColDoc.utils.log_debug
def plastex_engine(blobs_dir, fake_name, save_name, environ, uuid, lang, options,
                   levels = False, tok = False, strip_head = True, plastex_theme=None):
    " compiles the `fake_name` latex, and generates the `save_name` result ; note that extensions are missing "
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    _lang = ('_'+lang) if lang else ''
    #
    plastex_theme = options.get('plastex_theme','green')
    #
    fake_support=[]
    for es,ed in ColDoc.config.ColDoc_plastex_fakemain_reuse_extensions:
        f = 'main' + _lang + es
        a = osjoin(blobs_dir,f)
        if os.path.exists(a):
            logger.debug("Re-using %r as %r",f,fake_name+ed)
            shutil.copy2(a,fake_abs_name+ed)
            fake_support.append((a,fake_abs_name+ed))
        elif os.path.exists(save_abs_name+es):
            logger.debug("Re-using %r as %r",save_name+es,fake_name+ed)
            shutil.copy(save_abs_name+es,fake_abs_name+ed)
            fake_support.append((save_abs_name+es,fake_abs_name+ed))
        else:
            logger.debug("No %r -> %r file for this job",es,ed)
    #
    F = fake_name+'.tex'
    d = os.path.dirname(F)
    #assert os.path.isfile(F),F
    if d :
        logger.warning("The argument of `plastex` is not in the blobs directory: %r", F)
    #
    a,b = os.path.split(save_abs_name+'_html')
    save_name_tmp = tempfile.mkdtemp(dir=a,prefix=b)
    #
    argv = ['-d',save_name_tmp,"--renderer=HTML5", '--theme-css', plastex_theme]
    if not levels :
        argv += [ '--split-level', '-3']
    if tok is False or (environ[:2] == 'E_' and tok == 'auto'):
        argv.append( '--no-display-toc' )
    #n =  osjoin(blobs_dir,save_name+'_paux')
    #if not os.path.isdir(n):    os.mkdir(n)
    ## do not use ['--paux-dirs',save_name+'_paux'] until we understand what it does
    argv += ['--log',F]
    stdout_ = osjoin(blobs_dir,save_name+'_plastex.stdout')
    ret = ColDoc.utils.plastex_invoke(cwd_ =  blobs_dir ,
                         stdout_  = stdout_,
                         argv_ = argv,
                         logfile = fake_name+'.log')
    if os.path.exists(save_abs_name+'_html') :
        shutil.rmtree(save_abs_name+'_html')
    os.rename(save_name_tmp, save_abs_name+'_html')
    #
    if ret :
        logger.warning('Failed: cd %r ; plastex %s',blobs_dir,' '.join(argv))
    #
    extensions = ColDoc.config.ColDoc_plastex_fakemain_preserve_extension
    for e in extensions:
        if os.path.exists(save_abs_name+'_plastex'+e):
            a= save_abs_name+'_plastex'+e
            os.rename(a,a+'~')
        if os.path.exists(fake_abs_name+e):
            s, d = fake_name+e,save_name+'_plastex'+e
            logger.debug('Rename %r to %r ', s, d)
            s, d = fake_abs_name+e,save_abs_name+'_plastex'+e
            os.rename(s,d)
            if ret: logger.warning(' rename %r to %r',s,d)
    #
    a = osjoin(blobs_dir, save_name+'_html','index.html')
    if os.path.isfile(a):
        logger.info('created html version of %r ',save_abs_name)
        try:
            convert_html_to_text(a, save_abs_name + '_html.txt', options)
        except:
            logger.exception('while creating txt version of %r from html ',save_abs_name)
    else:
        logger.warning('no "index.html" in %r',save_name+'_html')
        return False
    #
    replacements = dedup_html(osjoin(blobs_dir, save_name+'_html'), options)
    # replace urls in html to point to dedup-ed stuff
    for f in os.listdir(osjoin(blobs_dir, save_name+'_html')):
        f = osjoin(blobs_dir, save_name+'_html', f)
        if f[-5:]=='.html':
            L = O = open(f).read()
            # ok, regular expressions may be cooler
            for p in  'href="' , 'src="' :
                for e in '"', '#':
                    for o,r in replacements:
                        L = L.replace(p+o+e , p+r+e)
            if L != O:
                os.rename(f,f+'~')
                with open(f,'w') as f_:
                    f_.write(L)
    #
    if strip_head:
        for f in os.listdir(osjoin(blobs_dir, save_name+'_html')):
            f = osjoin(blobs_dir, save_name+'_html', f)
            if f[-5:]=='.html':
                logger.debug('stripping <head> of %r ',f)
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

@ColDoc.utils.log_debug
def pdflatex_engine(blobs_dir, fake_name, save_name, environ, lang, options, repeat = None):
    " If repeat is None, it will be run twice if bib data or aux data changed"
    save_abs_name = os.path.join(blobs_dir, save_name)
    fake_abs_name = os.path.join(blobs_dir, fake_name)
    _lang = ('_'+lang) if lang else ''
    # 'main.aux' and 'main.bbl' are saved latex_main()
    for e in ColDoc.config.ColDoc_pdflatex_fakemain_reuse_extensions:
        f = 'main' + _lang + e
        a = os.path.join(blobs_dir,f)
        if os.path.exists(save_abs_name+e):
            logger.debug("Re-using %r for %r",save_name+e,fake_name+e)
            shutil.copy2(save_abs_name+e, fake_abs_name+e)
        elif os.path.exists(a):
            logger.debug("Re-using %r for %r (hoping for the best)",f,fake_name+e)
            shutil.copy2(a,fake_abs_name+e)
        else:
            logger.debug("No %r file for this job",e)
    #
    f = 'main' + _lang + '.aux'
    a = os.path.join(blobs_dir,f)
    if os.path.exists(a):
        with open(fake_abs_name+'.aux', 'a') as f_:
            for l in open(a):
                if l.startswith(r'\bibcite'):
                    f_.write(l)
    #
    extensions = ColDoc.config.ColDoc_pdflatex_fakemain_preserve_extensions
    #
    ## dunno what this may be useful for
    #for e in extensions:
    #    if e not in ('.tex','.aux','.bbl') and os.path.exists(fake_abs_name+e):
    #        logger.warning('Overwriting: %r',fake_abs_name+e)
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
    if r != 0:
        logger.debug('LaTeX failed %r will not run BiBTeX',r)
    subcommands = []
    if environ in ( 'main_file', 'E_document') and os.path.isfile(fake_abs_name+'.aux'):
        if '\\bibdata' in open(fake_abs_name+'.aux').read():
            subcommands.append( ('bibtex','.bbl','.blg') )
        #
        if os.path.isfile(fake_abs_name+'.idx'):
            subcommands.append( ('makeindex','.ind','.ilg') )
    #
    for cmd,cmdext,logext in subcommands:
        logger.debug('Running '+cmd)
        if os.path.isfile(fake_abs_name+cmdext):
            file_md5 = hashlib.md5(open(fake_abs_name+cmdext,'rb').read()).hexdigest()
        else:
            file_md5 = None
        p = subprocess.Popen([cmd,fake_name],
                             cwd=blobs_dir,stdin=open(os.devnull),
                             stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
        a = p.stdout.read()
        if p.wait() != 0:
            logger.warning('%s fails, see %r', cmd, save_abs_name+logext)
            logger.warning('%s output: %r', cmd, a)
        else:
            if os.path.isfile(fake_abs_name+cmdext):
                if file_md5 is None or file_md5 != hashlib.md5(open(fake_abs_name+cmdext,'rb').read()).hexdigest():
                    if repeat is None:
                        logger.debug('%s changed the %s file, will rerun',cmd,cmdext)
                        repeat = True
                    else:
                        logger.debug('%s changed the %s file',cmd,cmdext)
                else:
                    logger.debug('%s did not change the %s file',cmd,cmdext)
            else:
                logger.warning('%s failed to create the %s file',cmd,cmdext)
    #
    a = 'Rerun to get cross-references right'
    if r == 0:
        if repeat is None and a in  open(fake_abs_name+'.log').read():
            logger.debug('%r reports %r in log, will rerun',engine,a)
            repeat = True
        elif repeat is None:
            logger.debug('%r does not report %r in log, will not rerun',engine,a)
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
                    logger.info("Created pdf %r size %d"%(save_name+e,siz))
                else:
                    logger.warning("Created empty pdf %r "%(save_name+e,))
            a,b=fake_name+e,save_name+e
            logger.debug('Rename %r to %r',a,b)
            a,b=fake_abs_name+e,save_abs_name+e
            os.rename(a,b)
        else:
            if e not in ( '.pdf', '.aux' ) :
                logger.debug("Missing :%r"%(fake_abs_name+e,))
            else:
                logger.warning("Missing :%r"%(fake_abs_name+e,))
                if e=='.pdf': res=False
    return res


def latex_tree(blobs_dir, uuid=None, lang=None, warn=False, options={}, verbose_name=None, email_to=None):
    " latex the whole tree, starting from `uuid` "
    log_level = logging.WARNING if warn else logging.DEBUG
    #
    if isinstance(options, (str,bytes) ):
        # base64 accepts both bytes and str
        options = pickle.loads(base64.b64decode(options))
    #
    metadata_class = options.get('metadata_class')
    coldoc_dir = options.get('coldoc_dir')
    coldoc = options.get('coldoc')
    #
    if coldoc_dir is not None:
        options = prepare_options_for_latex(coldoc_dir, blobs_dir, metadata_class, coldoc, options)
    #
    if uuid is None:
        logger.warning('Assuming root_uuid = 001')
        uuid = '001'
    uuid_, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=uuid, uuid_dir=None,
                                                   blobs_dir = blobs_dir,
                                                   coldoc = coldoc,
                                                   metadata_class=metadata_class)
    #
    ret = True
    if metadata.environ in environments_we_wont_latex:
        logger.log(log_level, 'Cannot `latex` environ %r , UUID = %r'%(metadata.environ, uuid,))
    else:
        r = latex_uuid(blobs_dir, uuid=uuid, metadata=metadata, lang=lang, warn=warn, options=options)
        r = all(r.values())
        ret = ret and r
    for u in metadata.get('child_uuid'):
        logger.debug('moving down from node %r to node %r',uuid,u)
        r = latex_tree(blobs_dir, uuid=u, lang=lang, warn=warn, options=options)
        ret = ret and r
    return ret



def prepare_options_for_latex(coldoc_dir, blobs_dir, metadata_class, coldoc=None, options = None): 
    if options is None:
        options = {}
    ### get and set some options
    if coldoc is None:
        coldoc = options.get('coldoc')
    else:
        options['coldoc'] = coldoc
    options['coldoc_dir'] = coldoc_dir
    #
    try:
        blobinator_args = ColDoc.utils.get_blobinator_args(blobs_dir)
        options.update(blobinator_args)
    except:
        logger.exception('No blobinator_args')
    #
    a = osjoin(coldoc_dir, 'coldoc.json')
    if os.path.isfile( a ):
        coldoc_args = json.load(open(a))
        options.update(coldoc_args['fields'])
        #
        coldoc_root_uuid = options.get('root_uuid')
        if isinstance(coldoc_root_uuid,int):
            coldoc_root_uuid = ColDoc.utils.int_to_uuid(coldoc_root_uuid)
        options['root_uuid'] = coldoc_root_uuid
        #
        root_metadata = metadata_class.load_by_uuid(uuid=coldoc_root_uuid, coldoc=coldoc, basepath=blobs_dir)
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
    return options



def prepare_parser(cmd_help=cmd_help):
    # parse arguments
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser = argparse.ArgumentParser(description='Compile coldoc material, using `latex` and `plastex` ',
                                     epilog=cmd_help,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--uuid',help='UUID to work on/start from')
    parser.add_argument('--lang',help='language to work on')
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
    if args.lang:
        lang = ColDoc.utils.normalize_iso3(args.lang)
        if lang is None or len(lang) != 3:
            print(_('--language %r is not a recognized language code') % args.lang)
            print(_(' Please use ISO_639-3 codes, see https://en.wikipedia.org/wiki/ISO_639-3'))
            sys.exit(2)
        args.lang = lang
    #
    blobs_dir = args.blobs_dir
    assert os.path.isdir(blobs_dir), blobs_dir
    #
    args.coldoc_dir = coldoc_dir = os.path.dirname(os.path.dirname(blobs_dir))
    from ColDoc.utils import FMetadata
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, FMetadata)
    options['url_UUID'] = args.url_UUID
    #
    options["squash_helper"] = ColDoc.transform.squash_input_uuid
    options['metadata_class'] = ColDoc.utils.FMetadata
    return main_by_args(args,options)


def main_by_args(args,options):
    argv = args.command
    lang = args.lang
    blobs_dir = args.blobs_dir
    coldoc_dir = args.coldoc_dir
    loggerU = logging.getLogger('ColDoc.utils')
    level = 30 - 10 * args.verbose
    logger.setLevel(level)
    loggerU.setLevel(level)
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
        ret = latex_uuid(blobs_dir, uuid=UUID, lang=lang, options=options)
        ret = all(ret.values())
    elif argv[0] == 'tree':
        ret = latex_tree(blobs_dir, uuid=UUID, lang=lang, options=options)
    elif argv[0] == 'main_private':
        ret = latex_main(blobs_dir, uuid=UUID, lang=lang, options=options, access='private')
    elif argv[0] == 'main_public':
        ret = latex_anon(coldoc_dir, uuid=UUID, lang=lang, options=options, access='public')
    elif argv[0] == 'all':
        ret = latex_main(blobs_dir, uuid=UUID, lang=lang, options=options, access='private')
        ret &= latex_anon(coldoc_dir, uuid=UUID, lang=lang, options=options, access='public')
        ret &= latex_tree(blobs_dir, uuid=UUID, lang=lang, options=options)
    else:
        sys.stderr.write('Unknown command, see --help')
        return False
    return ret


if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

