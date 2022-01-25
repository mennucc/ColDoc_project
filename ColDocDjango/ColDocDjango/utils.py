import os, sys, mimetypes, http, json, re, functools
from os.path import join as osjoin

# taken from Django, for convenience
slug_re = re.compile(r'^[-a-zA-Z0-9_]+\Z')
number_re = re.compile(r'^[0-9]+\Z')

from django.contrib.auth.validators import UnicodeUsernameValidator
valid_user_re = UnicodeUsernameValidator().regex

import logging
logger = logging.getLogger(__name__)

import django


#https://stackoverflow.com/questions/25967759/django-get-permpermision-string
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.conf import settings
from django.utils.translation.trans_real import parse_accept_lang_header

try:
    import pycountry
except  ImportError:
    pycountry = None

@functools.lru_cache(maxsize=1024)
def http_to_iso_language(lang):
    # TODO implement subvariants somehow
    if '-' in lang:
        p = lang.index('-')
        lang = lang[:p]
    newlang = None
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
                        e += '('+access+')'
                        a += '&access='+access
                    latex_error_logs.append(  (e, a ) )
    except:
        logger.exception("While reading latex_return_codes")
    return latex_error_logs



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


