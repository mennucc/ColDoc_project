import os, sys, mimetypes, http, json, re, functools
from os.path import join as osjoin

# taken from Django, for convenience
slug_re = re.compile(r'^[-a-zA-Z0-9_]+\Z')
number_re = re.compile(r'^[0-9]+\Z')
letter_re = re.compile(r'^[a-zA-Z]+\Z')

from django.contrib.auth.validators import UnicodeUsernameValidator
valid_user_re = UnicodeUsernameValidator().regex

import logging
logger = logging.getLogger(__name__)

import django


from django.contrib import messages
#https://stackoverflow.com/questions/25967759/django-get-permpermision-string
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.conf import settings
from django.utils.translation.trans_real import parse_accept_lang_header
from django.utils.translation import gettext, gettext_lazy, gettext_noop
from django.db import transaction

from ColDocDjango.middleware import redirect_by_exception

from ColDoc.utils import prologue_length, iso3lang2iso2


if django.VERSION[0] >= 4 :
    _ = gettext_lazy
else:
    # in django 3 you cannot concatenate strings to lazy-strings
    _ = gettext


try:
    import pycountry
except  ImportError:
    pycountry = None

@functools.lru_cache(maxsize=1024)
def http_to_iso_language(lang):
    " converts ll-LL languages to 3 letter codes ; needs `pycountry` "
    # TODO implement subvariants somehow
    if '-' in lang:
        p = lang.index('-')
        lang = lang[:p]
    if '_' in lang:
        p = lang.index('_')
        lang = lang[:p]
    newlang = None
    if not letter_re.match(lang):
        return
    lang = lang.lower()
    if len(lang) == 2:
        try:
            newlang = pycountry.languages.get(alpha_2=lang).alpha_3
        except:
            newlang = None
            logger.warning('cannot recognize language %r',  lang)
    elif len(lang) == 3:
        newlang = lang
    else:
        logger.warning('cannot recognize language %r',  lang)
    return newlang

@functools.lru_cache(maxsize=1024)
def request_accept_language(accept, cookie):
    " returns dictionary language -> value"
    if pycountry is None:
        return {}
    lang_value = {}
    # cookie has precedence
    if cookie:
        lang_code = http_to_iso_language(cookie)
        if lang_code:
            lang_value[lang_code] = 2.0
    for lang,value in parse_accept_lang_header(accept):
        newlang = http_to_iso_language(lang)
        if newlang:
            lang_value[newlang] = max(value, lang_value.get(newlang,0) )
        else:
            logger.warning('in %r cannot recognize language %r',
                           accept, lang)
    return lang_value


def permission_str_to_model(perm, obj):
    " convert permission from `str` to `Permission` for that `obj`"
    if isinstance(perm,str):
        content_type = ContentType.objects.get_for_model(obj)
        perm =  Permission.objects.get(content_type = content_type, codename=perm)
    return perm


def convert_latex_return_codes(latex_return_codes, NICK, UUID):
    " returns a list of (program, language, access, extension, link, [])"
    latex_error_logs = []
    try:
        d = latex_return_codes
        if  d:
            d = json.loads(d)
            for k,v in d.items():
                if not v:
                    if ':' in k:
                        k = k.split(':')
                        if len(k) == 3:
                            e,l,access = k
                        else:
                            e,l = k
                            access = ''
                    else:
                        e,l = k,''
                    e_ = {'latex':'.log', 'plastex':'_plastex.log'}[e]
                    a = django.urls.reverse( 'UUID:log',   kwargs={'NICK':NICK,'UUID':UUID})
                    if a[-1] != '/': a += '/'
                    a += '?lang=%s&ext=%s'  % (l,e_)
                    if access:
                        a += '&access='+access
                    latex_error_logs.append(  (e, l, access, e_, a, []) )
    except:
        logger.exception("While reading latex_return_codes")
    return latex_error_logs

def latex_error_fix_line_numbers(blobs_dir, anon_dir, uuid, latex_error_logs, load_uuid, prefix='view'):
    " compute line number for latex errors"
    a = []
    try:
        for e_prog, e_language, e_access, e_extension, e_link, useless in latex_error_logs:
            __dir = anon_dir if e_access == 'public' else blobs_dir
            uuid_line_err = ColDoc.utils.parse_latex_log(__dir, uuid, e_language, e_extension, prefix=prefix)
            # correct for line number
            errors = []
            for err_uuid, line, err  in uuid_line_err:
                line = int(line)
                #
                m = load_uuid(err_uuid)
                L = m.get_languages()
                b = None
                if 'mul' in L:
                    f = ColDoc.utils.choose_blob(metadata=m, blobs_dir=blobs_dir , lang='mul', ext='.tex')[0]
                    b = open(f).read().splitlines()
                if b:
                    try:
                        # in `mul` files, the line number has to be adjusted to skip lines in different languages"
                        line = ColDoc.utils.line_with_language_lines(b, line, e_language)
                    except:
                        logger.exception('ColDoc.utils.line_with_language_lines({b},int({line}),e_language)'.format(line=line,b=b))
                # ingnore prologue lines
                line -= prologue_length(L[0], m.environ)
                errors.append( ( err_uuid, line, err) )
            a.append( (e_prog, e_language, e_access, e_extension, e_link, errors) )
    except:
        logger.exception('while reparsing latex error logs')
        return latex_error_logs
    else:
        return a

def get_email_for_user(user):
    " get verified primary email"
    if settings.USE_ALLAUTH:
        from allauth.account.models import EmailAddress
        email = EmailAddress.objects.get_primary(user)
        if email and email.verified:
            email = email.email
        else: email = None
    else:
        email = user.email
    return email

###################

def load_unicode_to_latex(coldoc_dir):
    " math_to_unicode.json as dict unicode -> latex"
    f = osjoin(coldoc_dir, 'math_to_unicode.json')
    if os.path.isfile(f):
        try:
            d = json.load(open(f))
            return {b:a for (a,b) in d.items()}
        except:
            logger.exception('while loading %r',f)
    return {}

def load_latex_to_unicode(coldoc_dir):
    " math_to_unicode.json as dict latex -> unicode"
    f = osjoin(coldoc_dir, 'math_to_unicode.json')
    if os.path.isfile(f):
        try:
            d = json.load(open(f))
            return d
        except:
            logger.exception('while loading %r',f)
    return {}


@functools.lru_cache()
def _load_math_to_unicode_cached(file_, mtime):
    " math_to_unicode.json as patterns for re.sub"
    b = json.load(open(file_))
    if isinstance(b,dict):
        b = b.items()
    l = []
    ok = re.compile(r'\\[a-zA-Z]+')
    for k,v in b:
        # only a proper LaTeX command can be accepted
        assert ok.fullmatch(k), k
        k = re.compile( '(\\' + k + r')([^a-zA-Z])' )
        v = chr(v) + r'\2'
        l.append( (k,v) )
    return l

def load_latex_to_unicode_resub(coldoc_dir):
    " math_to_unicode.json as list of pairs (pattern, repl) for re.sub"
    a = osjoin(coldoc_dir,'math_to_unicode.json')
    if os.path.isfile(a):
        try:
            return _load_math_to_unicode_cached(a, os.path.getmtime(a))
        except:
            logger.exception('while loading %r', a)
    return []

def math_to_unicode_convert(value, math_to_unicode):
    " use patterns obtained via `load_latex_to_unicode_resub` on `value` "
    if value and '\\' in value:
        for c,r in math_to_unicode:
            value = re.sub(c,r,value)
    return value

#################### parse for labels

from plasTeX.TeX import TeX
import ColDoc

re_newlabel = re.compile(r'\\newlabel\s*{\s*([^}]*)\s*}\s*{\s*(.*)\s*}')

def  parse_for_labels_workhorse(aux_name, blobs_dir, labels=None, mytex = None):
    " parse a LaTeX auxfile for labels"
    if labels is None:
        labels={}
    if not os.path.isabs(aux_name):
        aux_name = osjoin(blobs_dir, aux_name)
    if not  os.path.isfile(aux_name):
        logger.warning('File %r does not exists', aux_name)
        return {}
    for l in open(aux_name):
        l = l.strip()
        a='\\@input{'
        if l.startswith(a):
            l = l[len(a):-1]
            if not l.endswith('.aux'):
                logger.warning('Skipping input of file %r', l)
            else:
                if not os.path.isabs(l):
                    l = osjoin(blobs_dir, l)
                parse_for_labels_workhorse(l, blobs_dir, labels, mytex = mytex)
        if l.startswith('\\newlabel'):
            ## may use
            #mytex.input(l[9:])
            #c=mytex.readArgumentAndSource(type=str)[1]
            #n=mytex.readArgumentAndSource()[1]
            #print('a',a)
            #print('b',b)
            ## but we use the regexp
            for c,n in re_newlabel.findall(l):
                # metadata usually keep delimiters in the database
                c='{'+c+'}'
                ## using info from https://tex.stackexchange.com/questions/512148/reference-for-newlabel
                o = []
                # create JIT
                if mytex is None:
                    mytex = TeX()
                mytex.input(n)
                for i in range(5): #in mytex.readToken():
                    a=mytex.readArgumentAndSource()[1]
                    if a:
                        o.append(a)
                    else:
                        break
                o  = ('\t'.join(o))
                labels[c] = c, n, o, aux_name
    return labels

def   parse_for_labels_all_aux(coldoc_dir, blobs_dir, coldoc, metadata):
    "parse for latex labels all aux files (currently unused)"
    uuid_dir = ColDoc.utils.uuid_to_dir(metadata.uuid, blobs_dir=blobs_dir)
    langs = metadata.get_languages()
    if 'mul' in langs:
        langs = coldoc.get_languages()
    labels={}
    mytex = TeX()
    for base in 'blob','view':
        for lang in langs:
            aux_name = os.path.join(blobs_dir, uuid_dir , base + '_' + lang + '.aux')
            if os.path.exists(aux_name):
                parse_for_labels_workhorse(aux_name, blobs_dir, labels, mytex)
    #
    with transaction.atomic():
        metadata.delete2(key='AUX_label_'+lang)
        for c,n,o,a in labels.values():
            metadata.add2( key =  'AUX_label_'+lang, value = c, second_value = o)

def   parse_for_labels_callback(coldoc_dir, coldoc, #partialized
                                 return_values, blobs_dir, metadata,lang, save_name):
    aux_name = osjoin(blobs_dir, save_name + '.aux')
    if os.path.exists(aux_name):
        labels = parse_for_labels_workhorse(aux_name, blobs_dir)
        with transaction.atomic():
            metadata.delete2(key='AUX_label_'+lang)
            for t in labels.values():
                c,n,o,a = t
                metadata.add2( key =  'AUX_label_'+lang, value = c, second_value = o)
    else:
        logger.warning('Aux file does not exist: %r', aux_name)


#####


def check_login_timeout(request, NICK):
    " if the user is not authenticated, force a redirect to the coldoc index page"
    if not request.user.is_authenticated:
        messages.add_message(request,messages.WARNING, _('Session timeout, please login again'))
        redirect_by_exception(django.urls.reverse('ColDoc:index', kwargs={'NICK':NICK,} ))

######

def build_hreflang_links(path, view_ext, langs, CDlangs=None):
    if 'zxx' in langs or 'und' in langs:
        return []
    if view_ext:
        path += '?ext=' + view_ext 
    a = [ ('x-default', path) ]
    if view_ext:
        path += '&lang='
    else:
        path += '?lang='
    L = langs
    if CDlangs and 'mul' in langs:
        L = CDlangs
    for l in L:
        l2 = iso3lang2iso2(l)
        if l2:
            a.append( (l2, path + l ) )
    return a

def _fork_class_callback(f):
    if f.fork_type in ('simple',) and  settings.CLOSE_CONNECTION_ON_FORK:
        logger.critical('Using %s forks for subprocesses , is incompatible with certain databases',
                        f.fork_type)


def get_django_fork_class():
    #
    import coldoc_tasks.task_utils
    #
    return    coldoc_tasks.task_utils.choose_best_fork_class(getattr(settings,'COLDOC_TASKS_INFOFILE',None),
                                                             getattr(settings,'COLDOC_TASKS_CELERYCONFIG',None),
                                                             callback=_fork_class_callback)
