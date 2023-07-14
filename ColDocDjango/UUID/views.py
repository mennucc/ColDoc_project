import os, sys, mimetypes, http, copy, json, hashlib, difflib, shutil, subprocess, re, io, inspect, functools, tempfile
from html import escape as py_html_escape
import pickle, base64
from os.path import join as osjoin

try:
    import pycountry
except:
    pycountry = None

try:
    from bs4 import BeautifulSoup
except:
    BeautifulSoup = None

try:
    from pylatexenc.latex2text import LatexNodes2Text
except:
    LatexNodes2Text = None

try:
    import magic
except:
    magic = None

try:
    import lockfile
except:
    lockfile = None


import logging
logger = logging.getLogger(__name__)


import django
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse, QueryDict
from django.contrib import messages
from django import forms
from django.conf import settings
#from django.core import serializers
from django.core.exceptions import SuspiciousOperation, PermissionDenied
from django.utils.html import escape
from django.templatetags.static import static
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth.models import Group
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext, gettext_lazy, gettext_noop
from django.utils.text import format_lazy
from django.utils.functional import lazy
from django.views.decorators.csrf import csrf_exempt

full_escape_translate_lazy = lazy ( lambda s : py_html_escape(gettext_lazy (s ) , quote=True) , str )
full_escape_lazy = lazy ( lambda s : py_html_escape(s , quote=True) , str )


if django.VERSION[0] >= 4 :
    _ = gettext_lazy
else:
    # in django 3 you cannot concatenate strings to lazy-strings
    _ = gettext

if settings.USE_SELECT2 :
    from django_select2 import forms as s2forms

    class AuthorWidget(s2forms.ModelSelect2MultipleWidget):
        search_fields = [
            "username__icontains",
            "email__icontains",
        ]
else:
    AuthorWidget = django.forms.SelectMultiple


import plasTeX.Tokenizer
import plasTeX.Base as Base
from plasTeX.TeX import TeX
#from plasTeX.Packages import graphicx

import ColDoc.utils, ColDoc.latex, ColDocDjango, ColDocDjango.users
from ColDoc.utils import slug_re, slugp_re, is_image_blob, html2text, uuid_to_dir, gen_lang_metadata, strip_delimiters
from ColDoc.utils import langc_re , lang_re
from ColDocDjango.utils import get_email_for_user, load_unicode_to_latex, check_login_timeout
from ColDoc.blob_inator import _rewrite_section, _parse_obj
from ColDoc import TokenizerPassThru, transform
from ColDocApp import text_catalog
from ColDoc.utils import iso3lang2word as iso3lang2word_untranslated
from ColDocDjango.utils import convert_latex_return_codes, latex_error_fix_line_numbers
from ColDocDjango.middleware import redirect_by_exception

import coldoc_tasks.task_utils

def _fork_class_callback(f):
    if f.fork_type in ('simple',) and  settings.CLOSE_CONNECTION_ON_FORK:
        logger.critical('Using %s forks for subprocesses , is incompatible with certain databases',
                        f.fork_type)

fork_class_default = \
    coldoc_tasks.task_utils.choose_best_fork_class(getattr(settings,'COLDOC_TASKS_INFOFILE',None),
                                                   getattr(settings,'COLDOC_TASKS_CELERYCONFIG',None),
                                                   callback=_fork_class_callback)



def iso3lang2word(*v , **k):
    return gettext_lazy(iso3lang2word_untranslated(*v, **k))

def iso3lang2word_H(*v , **k):
    # do not show header 'Undetermined' or 'No linguistic content
    if v[0] in ('zxx','und'):
        return ''
    return gettext_lazy(iso3lang2word_untranslated(*v, **k))


from .models import DMetadata, DColDoc, uuid_replaced_by

from .shop import encoded_contract_to_buy_permission, can_buy_permission

def int_(v):
    try:
        return int(v)
    except:
        logger.exception('Problem with %r',v)
    return 0


wrong_choice_list = [('internal_error','internal_error')]

##############################################################
def __redirect_other_lang(request,lang,ext):
    "  courtesy for people using other language codes "
    if lang is not None and not langc_re.match(lang) and pycountry:
        a = ColDocDjango.utils.http_to_iso_language(lang)
        if a:
            b = request.path + '?lang=' + a
            if ext:
                b += '&ext=' + ext
            logger.warning('Redirected %r %r %r to %r',request.path, lang, ext , b)
            redirect_by_exception(request.build_absolute_uri(b), permanent=True)


##############################################################

class PurchaseEncodedForm(forms.Form):
    encoded = forms.CharField(widget=forms.HiddenInput())

##############################################################

class MetadataForm(forms.ModelForm):
    class Meta:
        model = DMetadata
        fields = ['author', 'access', 'environ','optarg','latex_documentclass_choice']
        widgets = {
                    "author": AuthorWidget,
                    'environ': django.forms.Select(choices=[('invalid','invalid')])
                  }
    # record these values from submitter
    uuid_  = forms.CharField(widget=forms.HiddenInput())
    ext_  = forms.CharField(widget=forms.HiddenInput())
    lang_ = forms.CharField(widget=forms.HiddenInput(),required = False)    

###############################################################

class LangForm(forms.Form):
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        choice_list = kwargs.pop('choice_list')
        super(LangForm, self).__init__(*args, **kwargs)
        if kwargs.get('prefix') in ('multlang','manual'):
            if choice_list != wrong_choice_list:
                logger.error('internal inconsistency')
            self.fields['langchoice'] = forms.CharField(widget=forms.HiddenInput(),required=False)
        else:
            self.fields['langchoice'] = forms.ChoiceField(choices=choice_list,
                                                      label=_("Language"),
                                                      #help_text="Language choice"
                                                      )

    class Meta:
        fields = ('langchoice', )


# show prologue in web UI, to ease debugging
__debug_view_prologue__ = False


class BlobUploadForm(forms.Form):
    htmlid = "id_form_blobuploadform"
    file = forms.FileField(help_text=_("File to upload"))
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput(),required = False)
    #oldext = forms.CharField(widget=forms.HiddenInput(),required = False)    

class BlobEditForm(forms.Form):
    #
    def __init__(self, *args, **kwargs):
        filters = kwargs.pop('latex_filters',transform.get_latex_filters())
        super().__init__(*args, **kwargs)
        for name, label, help, val, fun in filters:
            field = forms.BooleanField(label=label,required = False,widget = forms.CheckboxInput(),help_text=help, initial=val)
            self.fields[name] = field
    #
    class Media:
        js = ('UUID/js/blobeditform.js',)
    htmlid = "id_form_blobeditform"
    ## remembers first line of sections, or \uuid when present
    prologue = forms.CharField(widget = forms.TextInput(attrs={'class': 'form-text w-75'}) \
                               if __debug_view_prologue__ else \
                               forms.HiddenInput(),
                               required = False, label=_('Prologue'),
                               help_text=_('First line of text file, automatically generated'))
    # the real blobcontent
    shortprologue = forms.CharField(widget = forms.TextInput(attrs={'class': 'form-text w-75'}) \
                               if __debug_view_prologue__ else \
                               forms.HiddenInput(),
                               required = False, label=_('Short Prologue'),
                               help_text=_('First line of text file,  short version, automatically generated'))
    blobcontent = forms.CharField(widget=forms.HiddenInput(),required = False)
    # what the user can edit
    BlobEditTextarea=forms.CharField(label=_('Blob content'),required = False,
                                     widget=forms.Textarea(attrs={'class': 'form-text w-100'}),
                                     help_text=_('Edit the blob content'))
    BlobEditComment=forms.CharField(label=_('Comment'),required = False,
                                    widget=forms.TextInput(attrs={'class': 'form-text w-75'})
                                        if settings.USE_COMMIT_COMMENTS
                                        else forms.HiddenInput(),
                                    help_text=_('Comment for this commit'))
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput(),required = False)
    file_md5 = forms.CharField(widget=forms.HiddenInput())
    selection_start = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    selection_end = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    split_selection = forms.BooleanField(label=_('Insert a child node'),required = False,
                                         widget = forms.CheckboxInput(attrs = {'onclick' : "hide_and_show();", }),
                                         help_text=_("Insert a child node at cursor (if a piece of text is selected, it will be moved into the child)"))
    split_environment = forms.ChoiceField(label=_("Environment"),
                                          help_text=_("Environment for newly created blob"))
    split_add_beginend = forms.BooleanField(label=_('Add begin/end'),required = False,
                                            help_text=_("add a begin{}..end{} around the splitted part"))

def common_checks(request, NICK, UUID, accept_anon=False):
    assert isinstance(NICK,str) and isinstance(UUID,str)
    if not slug_re.match(UUID):
        logger.error('ip=%r user=%r coldoc=%r uuid=%r  : invalid UUID',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
        raise SuspiciousOperation("Invalid UUID %r." % (UUID,))
    if not slug_re.match(NICK):
        logger.error('ip=%r user=%r coldoc=%r uuid=%r  : invalid NICK',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
        raise SuspiciousOperation("Invalid ColDoc %r." % (NICK,))
    if (not accept_anon) and  request.user.is_anonymous:
        logger.error('ip=%r coldoc=%r uuid=%r  : is anonymous',
                       request.META.get('REMOTE_ADDR'), NICK, UUID)
        raise SuspiciousOperation("Permission denied")
    #
    try:
        coldoc = DColDoc.objects.get(nickname = NICK)
    except DColDoc.DoesNotExist:
        raise SuspiciousOperation("No such ColDoc %r.\n" % (NICK,))
    #
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    if not os.path.isdir(blobs_dir):
        raise SuspiciousOperation("No blobs for this ColDoc %r.\n" % (NICK,))
    return coldoc, coldoc_dir, blobs_dir




def decorator_url(_do_lock=True, **_decorator_kwargs):
    """ `cmd` must be called with `request` `NICK`, `UUID` ,
    `cmd`  be  called with args: request, NICK, UUID, coldoc, metadata, coldoc_dir, blobs_dir, uuid_dir, **kwargs
     and with a lock in the blob directory"; an argument of `ajax_actions`  has a special meaning """
    def inner_decorator(_cmd):
        @functools.wraps(_cmd)
        def wrapper(request, *_kargs, **_wargs):
            assert not _kargs
            NICK = _wargs.get('NICK')
            UUID = _wargs.get('UUID')
            #
            if request.method != 'POST' :
                return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
            #
            if request.user.is_anonymous:
                m = _('Session timeout, please login again')
                b = ajax_actions = _decorator_kwargs.get('ajax_actions',())
                if any ( (a in request.POST) for a in b ):
                    return JsonResponse({"alert":json.dumps(str(m))})
                messages.add_message(request,messages.ERROR, m)
                return redirect(django.urls.reverse('ColDoc:index', kwargs={'NICK':NICK,} ))
            #
            coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
            #
            metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
            #
            if metadata is None:
                raise SuspiciousOperation('No such nick %r uuid %r' % (NICK,UUID) )
            #
            uuid_dir = uuid_to_dir(UUID)
            if not os.path.isdir(osjoin(blobs_dir, uuid_dir)):
                raise SuspiciousOperation('No directory for nick %r uuid %r' % (NICK,UUID) )
            #
            do_lock = _do_lock and lockfile
            #
            l = locals()
            l.update(_decorator_kwargs)
            _wargs.update( (j,l[j]) for j in l if (not j.startswith('_') and len(l) > 2))
            if do_lock:
                lock = lockfile.LockFile(osjoin(settings.COLDOC_SITE_ROOT, 'lock', 'lock_' + NICK + '_' + UUID))
                with lock:
                    return _cmd(**_wargs)
            else:
                return _cmd(**_wargs)
        return wrapper
    return inner_decorator



def __extract_prologue(blobcontent, uuid, env, optarg):
    prologue = ''
    shortprologue = ''
    blobeditdata = blobcontent
    warnings = []
    try:
        if isinstance(optarg , str):
            if not optarg:
                optarg = []
            else:
                optarg = json.loads(optarg)
    except:
        logger.exception('While parsing optarg %r', optarg)
        warnings.append(_('Internal error when parsing optarg %r for  blob %r ') % (optarg,uuid))
        optarg = []
    if env in ColDoc.config.ColDoc_environments_sectioning:
        a = '\\ColDocUUIDcheckpoint\n'
        if blobcontent.startswith(a):
            blobcontent = blobcontent[len(a):]
        if blobcontent.startswith('\\'+env):
            try:
                j = blobcontent.index('\n')
                prologue = blobcontent[:j]
                if optarg:
                    shortprologue = '\\' + env + ''.join(optarg) 
                    shortprologue = re.sub(' +', ' ', shortprologue)
                    blobeditdata = shortprologue + '\n' + blobcontent[j+1:]
                else:
                    warnings.append('Missing initial \\%s line' % env)
                    logger.error('Blob %r does not have optarg for %s',uuid, env)
            except:
                warnings.append('Internal error when analyzing  blob %r ' % (uuid,))
                logger.exception('Could not normalize section blob %r', uuid)
                prologue = '%'
        else:
            if optarg:
                shortprologue = '\\' + env + ''.join(optarg) 
                blobeditdata = shortprologue + '\n' + blobcontent
                warnings.append(_('Added initial \\%s line') % env)
            else:
                warnings.append(_('Missing initial \\%s line') % env)
    elif env not in ColDoc.config.ColDoc_do_not_write_uuid_in:
        if not blobcontent.startswith('\\uuid'):
            logger.error('Blob %r does not start with \\uuid',uuid)
            warnings.append(_('Missing initial, hidden, \\uuid line in blob %r') % (uuid,))
            prologue = '\\uuid{%s}%%' % (uuid,)
        else:
            try:
                j = blobcontent.index('\n')
                prologue = blobcontent[:j]
                blobeditdata = blobcontent[j+1:]
            except:
                logger.exception('Could not remove uuid line from blob %r', uuid)
                prologue = '%'
    # if the above code is changed, then prologue_length() must be changed as well
    return shortprologue, prologue, blobeditdata, warnings

def _build_blobeditform_data(metadata,
                             user, filename,
                             ext, lang,
                             choices,
                             can_add_blob, can_change_blob,
                             msgs,
                             latex_filters = [],
                             ):
    #
    NICK = metadata.coldoc.nickname
    UUID = metadata.uuid
    env = metadata.environ
    optarg = metadata.optarg
    #
    uncompiled = 0
    file_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    blobcontent = open(filename).read()
    if blobcontent and blobcontent[-1] != '\n' :
        blobcontent += '\n'
    # the first line contains the \uuid command or the \section{}\uuid{}
    shortprologue, prologue, blobeditdata, warnings = __extract_prologue(blobcontent, UUID, env, optarg)
    if '\\uuid{' in blobeditdata:
        warnings.append(_('(Why is there a  \\uuid  in this blob ?)'))
    for wp in warnings:
        msgs.append(( messages.WARNING, wp))
    #
    user_id = str(user.id)
    a = filename[:-4] + '_' + user_id + '_editstate.json'
    #
    D = {'BlobEditTextarea':  blobeditdata,
         'prologue' :  prologue,
         'shortprologue' : shortprologue,
         'blobcontent' : blobcontent,
         'NICK':NICK,'UUID':UUID,'ext':ext,'lang':lang,
         'file_md5' : file_md5,
         }
    #
    N = {}
    if os.path.isfile(a):
        m = None
        # if the editstate is corrupt, ignore it
        try:
            N=(json.load(open(a)))
            if N['ext'] != ext:
                m = 'editstate ext %r != %r ' % (N['ext'],ext)
            elif N['lang'] != lang:
                m = 'editstate lang %r != %r ' % (N['lang'],lang)
            elif N['UUID'] != UUID:
                m = 'editstate uuid %r != %r ' % (N['UUID'],UUID)
        except Exception as e:
            logger.exception('while loading %r',a)
            m = repr(e)
        if m:
            logger.warning(m)
            msgs.append(( messages.WARNING, 
                        _('Editstate ignored') + ': ' + m ))
            N ={}
    if N:
        if N['file_md5'] != file_md5:
            msgs.append(( messages.WARNING,
                         _('File was changed on disk since your last visit')))
            N['file_md5'] = file_md5
        elif 'blobcontent' in N and N['blobcontent'] != blobcontent:
            uncompiled = 1
            msgs.append(( messages.INFO,
                          _('Your saved changes are yet uncompiled') ))
        D.update(N)
    #
    if settings.USE_CODEMIRROR:
        lines = blobeditdata.splitlines(keepends = True)
        a = int_(D.get('selection_start',0))
        line , ch = ColDoc.utils.text_pos2linechar(lines, a)
        D['selection_start'] = json.dumps({'line': line, 'ch': ch })
        a = int_(D.get('selection_end',0))
        line , ch = ColDoc.utils.text_pos2linechar(lines, a)
        D['selection_end'] = json.dumps({'line': line, 'ch': ch })
    #
    blobeditform = BlobEditForm(initial=D, latex_filters=latex_filters) #, prefix='BlobEditForm')
    blobeditform.fields['split_environment'].choices = choices
    #
    if __debug_view_prologue__:
        blobeditform.fields['prologue'].widget.attrs['readonly'] = True
    #
    if not can_change_blob:
        blobeditform.fields['BlobEditTextarea'].widget.attrs['readonly'] = True
        blobeditform.fields['BlobEditTextarea'].widget.attrs['disabled'] = True
    if not can_add_blob:
        blobeditform.fields['split_selection'].widget.attrs['readonly'] = True
        blobeditform.fields['split_selection'].widget.attrs['disabled'] = True
    return blobeditform, uncompiled

re_md5 = re.compile('^(blob|view|main)_[a-z][a-z][a-z]((\.[a-z][a-z]*)|_html/index.html)$')

def md5(request, NICK, UUID, ACCESS, FILE):
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID, accept_anon=True)
    assert  isinstance(FILE,str)
    if not re_md5.match(FILE):
        raise SuspiciousOperation("Malformed file: "+repr(FILE))
    #
    metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
    if metadata is None:
        return HttpResponse('UUID not found', status=http.HTTPStatus.NOT_FOUND)
    #
    # TODO SuspiciousOperation may be raised when login has expired
    #
    if FILE.startswith('main'):
        assert UUID == coldoc.root_uuid
        if ACCESS not in ('private', 'public'):
            raise SuspiciousOperation("Wrong access")
        request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
        a = request.user.has_perm('UUID.view_view')
        if (not a) and ACCESS == 'private':
            raise SuspiciousOperation("Mismatched access (login timed out?)")
        if ACCESS == 'public':
            blobs_dir = osjoin(coldoc_dir, 'anon')
    elif FILE.startswith('view'):
        request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
        if not request.user.has_perm('UUID.view_view'):
            logger.error('Hacking attempt %r',request.META)
            raise SuspiciousOperation("Permission denied")
    elif FILE.startswith('blob'):
        request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
        if not request.user.has_perm('UUID.view_blob'):
            logger.error('Hacking attempt %r',request.META)
            raise SuspiciousOperation("Permission denied")
    else:
        raise RuntimeError('should not reach this')
    from ColDoc.utils import uuid_to_dir
    filename = osjoin(blobs_dir, uuid_to_dir(UUID), FILE)
    if not os.path.isfile(filename):
        return HttpResponse('File not found', status=http.HTTPStatus.NOT_FOUND)
    real_file_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    real_file_mtime = str(os.path.getmtime(filename))
    return JsonResponse({'file_md5':real_file_md5, 'file_mtime': real_file_mtime})


def _interested_emails(coldoc,metadata):
    # add email of authors of this blob
    email_to = [ ]
    for au in metadata.author.all():
        a = get_email_for_user(au)
        if a is not None and a not in email_to:
            email_to.append(a)
    # add emails of editors
    try:
        n = ColDocDjango.users.name_of_group_for_coldoc(coldoc.nickname, 'editors')
        gr = Group.objects.get(name = n)
        for ed in gr.user_set.all():
            a = get_email_for_user(ed)
            if a is not None  and a not in email_to:
                email_to.append(a)
    except:
        logger.exception('While adding emails of editors for coldoc %r',coldoc.nickname)
    return email_to

def _parse_for_section(blobeditarea, env, uuid, weird_prologue):
    " split `prologue` section from `blobeditarea` ;\
    return  `prologue`  `newblobeditarea` `sources`"
    newprologue = ''
    output = ''
    sources = None
    warn_notfirst_ = False
    warn_dup_ = False
    # give it some context
    thetex = TeX()
    #thetex.ownerDocument.context.loadPackage(thetex, 'article.cls', {})
    ## add to `initial` lines up to the first empty line
    b = blobeditarea.splitlines()
    initial = ''
    while b and not b[0].strip():
        # remove empty lines
        b.pop(0)
    if b and b[0].strip() == r'\ColDocUUIDcheckpoint':
        b.pop(0)
    while b and b[0].strip():
        # add up to next empty line
        initial += b[0] + '\n'
        b.pop(0)
    rest = '\n'.join(b) + ( '\n' if b else '')
    # parse `initial` part for `env` macros , distinguishing for different languages
    thetex.input(initial,  Tokenizer=TokenizerPassThru.TokenizerPassThru)
    thetex.currentInput[0].pass_comments = True
    itertokens = thetex.itertokens()
    lang = None
    sources_by_langs = {}
    ccp = ColDoc.config.ColDoc_language_header_prefix
    if ccp.startswith( '\\') :
        ccp = ccp[1:]
    while itertokens is not None:
        try:
            tok = next(itertokens)
        except StopIteration:
            itertokens = None
            break
        if isinstance(tok, TokenizerPassThru.Comment):
            output += '%' + str(tok)
        elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
            macroname = str(tok.macroName)
            if macroname.startswith(ccp):
                lang = macroname[len(ccp):]
                output += '\\' + str(tok)
            elif not macroname == env:
                if str(tok).startswith('active::'):
                    output += tok.source
                else:
                    output += '\\' + str(tok)
            elif lang not in sources_by_langs :
                obj = Base.section()
                thetex.currentInput[0].pass_comments = False
                src, sources, attributes = _parse_obj(obj, thetex)
                thetex.currentInput[0].pass_comments = True
                if any([ ('\n' in s) for s in sources]):
                    weird_prologue.append(_('Keep the\\%s{...} command all in one line.') % (env,))
                    sources = list(map( lambda x : x.replace('\n',' '), sources ))
                sources_by_langs[lang] = sources
            else:
                warn_dup_ = True
                if str(tok).startswith('active::'):
                    output += tok.source
                else:
                    output += '\\' + str(tok)
        else:
            if isinstance(tok, TokenizerPassThru.Space) and str(tok) == '\n':
                lang = None
            output += tok.source
            if not isinstance(tok, TokenizerPassThru.Space) and not sources_by_langs :
                warn_notfirst_ = True
    if not sources_by_langs :
        weird_prologue.append(_('Please add a \\%s{...} command in first line.') % (env,))
    elif warn_notfirst_:
        weird_prologue.append(_('The command \\%s{...} was moved to first line.') % (env,))
        newprologue += '%\n'
    if warn_dup_ :
        weird_prologue.append(_('The blob should contain only one occurrence of \\%s{...}.') % (env,))
    # combine all `env` for all languages in one and only one, using language conditionals
    sources = ['', '', '']
    d1l = ''
    cci = ColDoc.config.ColDoc_language_conditional_infix
    for k,v in sources_by_langs.items():
        # process star argument
        # note that only the last one will be effective
        sources[0] = v[0]
        # process [] and {} arguments
        a1 = a2 = ''
        d1l, v1 , d1r = strip_delimiters(v[1],'[]')
        d2l, v2 , d2r = strip_delimiters(v[2])
        if k is not None:
            a2 = r'\fi '
            a1 = r'\if' + cci + k + ' '
        if v1:
            sources[1] += a1 + v1 + a2
        if v2:
            sources[2] += a1 + v2 + a2
    # FIXME an empty  [] option may be destroyed, the user should use [~]
    if sources[1] or d1l:
        sources[1]  = '[' + sources[1] + ']'
    sources[2]  = '{' + sources[2] + '}'
    ignoreme, newprologue = _rewrite_section(sources, uuid, env)
    #
    # avoid duplicated spaces
    newprologue = re.sub(' +', ' ', newprologue)
    newprologue = newprologue.rstrip('\n') + '\n'
    output = output.lstrip()
    if output and output[-1] != '\n':
        logger.warning('missing new line %r',output)
        output += '\n'
    return newprologue, (output + rest), sources

def   _put_back_prologue(prologue, blobeditarea, env, uuid):
    " for sections, analyze edited `blobeditarea` to get new parameters for `prologue`;\
    then add `prologue` to `blobeditarea` to recreate `blobcontent`;\
    return `blobcontent`, `newprologue`, `sources` , `weird_prologue`, `displacement` \
    that is how much the text was displaced from  `blobeditarea` to `newblobeditarea`"
    sources = None
    weird_prologue = []
    newprologue = ''
    displacement = 0
    if env in ColDoc.config.ColDoc_environments_sectioning :
        # try to parse \\section
        try:
            #
            newprologue, b, sources = _parse_for_section(blobeditarea, env, uuid, weird_prologue)
            displacement = len(b)- len(blobeditarea)
            blobeditarea = b
            newprologue = '\\ColDocUUIDcheckpoint\n' + newprologue
        except:
            logger.exception('While parsing \\section')
            weird_prologue.append(_('Internal error while parsing for \\%s{...}.') % (env,))
        blobcontent = newprologue + blobeditarea
        displacement += len(newprologue)
    elif env not in ColDoc.config.ColDoc_do_not_write_uuid_in:
        newprologue = '\\uuid{%s}%%\n' % (uuid,)
        blobcontent = newprologue + blobeditarea
        displacement = len(newprologue)
    else:        
        blobcontent = blobeditarea
    return blobcontent, newprologue, sources , weird_prologue, displacement

@decorator_url()
def postlang(request, NICK, UUID, coldoc, coldoc_dir, blobs_dir, metadata, **w):
    #
    actions = ['add','translate','relabel','delete','multlang','manual']
    prefix = request.POST.get('button')
    if prefix not in actions:
        raise SuspiciousOperation("Wrong action: %r"%prefix)
    #
    Clangs = coldoc.get_languages()
    l = Clangs + ['mul','zxx','und']
    ll = [(a,a) for a in l]
    if prefix in ('multlang', 'manual'):
        ll = wrong_choice_list
    form=LangForm(data=request.POST, prefix=prefix, choice_list=ll)
    #
    if not form.is_valid():
        a = "Invalid form: "+repr(form.errors)
        return HttpResponse(a,status=http.HTTPStatus.BAD_REQUEST)
    #
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    langchoice_ = form.cleaned_data['langchoice']
    assert UUID == uuid_ and NICK == nick_
    assert lang_re.match(lang_)
    assert slugp_re.match(ext_)
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    can_change_blob = request.user.has_perm('UUID.change_blob')
    can_change_metadata = request.user.has_perm('UUID.change_dmetadata')
    #can_add_blob = request.user.has_perm('ColDocApp.add_blob')
    if not (can_change_metadata and can_change_blob):
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    log = functools.partial(messages.add_message,request)
    ret = postlang_no_http(log, metadata, prefix, lang_, ext_ , langchoice_ )
    a = 'compilation_in_progress_' + metadata.uuid
    if a not in request.session:
        metadata.refresh_from_db()
        fork1 = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, metadata, fork=True)
        request.session[a] = base64.a85encode(pickle.dumps((fork1,None))).decode('ascii')
        request.session.save()
    return ret

def postlang_no_http(logmessage, metadata, prefix, lang_, ext_ , langchoice_):
    coldoc = metadata.coldoc
    NICK = metadata.coldoc.nickname
    UUID = metadata.uuid
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    assert os.path.isdir(blobs_dir)
    Clangs = coldoc.get_languages()
    #
    D = uuid_to_dir(UUID, blobs_dir)
    D = osjoin(blobs_dir, D)
    #
    try:
        os.unlink(osjoin(D,'.check_ok'))
    except OSError:
        pass
    #
    def set_lang(lang):
        with transaction.atomic():
            m = metadata.locked_fresh_copy()
            m.lang = lang
            m.save()
        metadata.refresh_from_db()
    #
    Blangs = metadata.get_languages()
    if prefix == 'manual':
        assert len(Blangs) == 1 and 'mul' in Blangs
        for l in Clangs:
            src = osjoin(D,'blob_' + l + ext_)
            if os.path.isfile(src):
                lines = open(src).readlines()
                if lines and lines[0].startswith(ColDoc.config.ColDoc_auto_line1):
                    lines.pop(0)
                if lines and lines[0].startswith(ColDoc.config.ColDoc_auto_line2):
                    lines.pop(0)
                os.rename(src,src+'~auto~')
                with open(src,'w') as f_:
                    f_.write(''.join(lines))
        set_lang( '\n'.join(Clangs) + '\n' )
        logmessage(messages.INFO,_('Converted to manual language management (non <tt>mul</tt>)'))
        dst = osjoin(D,'blob_mul'+ext_)
        if os.path.exists(dst):
            os.rename(dst,dst+'~disable~')
        ColDoc.utils.recreate_symlinks(metadata, blobs_dir)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?ext=%s'%(ext_) )
    #
    if prefix == 'multlang' and len(Blangs) == 1:
        if LatexNodes2Text is None:
            a='You may wish to install `pylatexenc` to improve the quality of these conversions'
            logmessage(messages.WARNING, a)
            logger.warning(a)
        origlang = Blangs[0]
        src = osjoin(D,'blob_' + origlang + ext_)
        dst = osjoin(D,'blob_mul'+ext_)
        string = open(src).read()
        string = ColDoc.utils.replace_language_in_inputs(string, origlang, 'mul')
        if os.path.exists(dst):
            os.rename(dst,dst+'~old~')
        F = open(dst,'w')
        for line in string.splitlines():
            if LatexNodes2Text is not None:
                try:
                    text = LatexNodes2Text().latex_to_text(line)
                except:
                    logger.exception('while LatexNodes2Text().latex_to_text on %r',line)
                    text = line
            else:
                text = line
            text = text.strip()
            if text:
                F.write(ColDoc.config.ColDoc_language_header_prefix + origlang + ' ' + line + '\n')
            else:
                F.write(line + '\n')
        # close it. This flushes the content. Otherwise sometimes the file appears empty in the web interface
        F.close()
        #
        set_lang('mul\n')
        logmessage(messages.INFO, _('Converted to `mul` method'))
        gen_lang_metadata(metadata, blobs_dir, Clangs)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + \
                        '?lang=mul&ext=%s'%(ext_) )
    #
    if prefix == 'multlang':
        dst = osjoin(D,'blob_mul'+ext_)
        sources = {}
        for ll in Clangs:
            llll = ColDoc.config.ColDoc_language_header_prefix + ll + ' '
            src = osjoin(D,'blob_'+ll+ext_)
            if os.path.isfile(src):
                string = open(src).read()
                string = ColDoc.utils.replace_language_in_inputs(string, ll, 'mul')
                sources[llll] = string.splitlines()
        try:
            output = ColDoc.utils.multimerge_lookahead(copy.deepcopy(sources),'')
        except:
            logger.exception('internal error')
            output = ColDoc.utils.multimerge(sources)
        output = [ (''.join(a)) for a in output ]
        if os.path.exists(dst):
            os.rename(dst,dst+'~old~')
        with open(dst,'w') as f_:
            f_.write('\n'.join(output) + '\n')
        set_lang( 'mul\n' )
        logmessage(messages.INFO,_('Converted to `mul` method'))
        gen_lang_metadata(metadata, blobs_dir, Clangs)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + \
                        '?lang=mul&ext=%s'%(ext_) )
    #
    dst = osjoin(D,'blob_'+langchoice_+ext_)
    src = osjoin(D,'blob_'+lang_+ext_)
    #
    redirectlang_ = langchoice_
    #
    if not os.path.exists(src):
        logmessage(messages.WARNING,
                             _('A blob with language %(lang)r extension %(ext)r does not exist') %
                             {'lang':iso3lang2word(lang_),'ext':ext_})
        logger.warning('A blob with language %r extension %r does not exist' % (lang_,ext_))
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    if prefix in ( 'add', 'translate', 'relabel'):
        L = metadata.get_languages()
        #
        if prefix == 'add' and os.path.exists(dst+'~disable~'):
            os.rename(dst+'~disable~', dst)
        #
        if os.path.exists(dst):
            logmessage(messages.WARNING,
                                 _('A blob with language %(lang)r extension %(ext)r already exists') %
                                 {'lang':iso3lang2word(lang_),'ext':ext_})
        else:
            if prefix in ( 'add', 'translate' ): # this never happens or langchoice_ == 'mul':
                if langchoice_ not in L:
                    set_lang( '\n'.join(L + [langchoice_]) + '\n' )
                    L = metadata.get_languages()
                logger.warning('copy %r to %r',src,dst)
                string = open(src).read()
                string = ColDoc.utils.replace_language_in_inputs(string, lang_, langchoice_)
                m = _('A blob with language %(newlang)r extension %(ext)r was created copying from %(oldlang)r.')%\
                    {'newlang':iso3lang2word(langchoice_),'ext':ext_, 'oldlang':iso3lang2word(lang_)}
                m = format_lazy('{}\n{}', m, _('Please check it.'))
                if settings.TRANSLATOR is not None and  prefix == 'translate':
                    try:
                        from ColDoc.latex import prepare_options_for_latex
                        options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, metadata.coldoc)
                        helper = transform.squash_helper_token2unicode
                        out = io.StringIO()
                        inp = io.StringIO(string)
                        inp.name = '%s / %s (%s)' %(NICK, UUID, lang_)
                        helper = transform.squash_latex(inp, out, options, helper)
                        translated = settings.TRANSLATOR(out.getvalue(), lang_, langchoice_)
                        string = transform.unsquash_unicode2token(translated, helper)
                        m = _('A blob with language %(newlang)r extension %(ext)r was automatically translated (%(len)d chars) from %(oldlang)r.')%\
                            {'newlang':iso3lang2word(langchoice_),'ext':ext_, 'oldlang':iso3lang2word(lang_),
                             'len':len(out.getvalue())} + '\n' + _('Please check it.')
                    except:
                        logmessage(messages.WARNING, _('The automatic translation failed'))
                        logger.exception('Failed translation from %r to %r of %r', lang_, langchoice_, string)
                with open(dst,'w') as f_:
                    f_.write(string)
                logmessage(messages.INFO, m)
            elif prefix == 'relabel':
                L[L.index(lang_)] = langchoice_
                set_lang( '\n'.join(L) + '\n' )
                logger.warning('rename %r to %r (converting language inputs)',src,dst)
                string = open(src).read()
                string = ColDoc.utils.replace_language_in_inputs(string, lang_, langchoice_)
                with open(dst,'w') as f_:
                    f_.write(string)
                os.unlink(src)
                assert langchoice_ != 'mul'
                for j in os.listdir(D):
                    for p in ('blob_', 'view_','squash_'):
                        if j.startswith(p + lang_):
                            h = p + langchoice_ + j[(3+len(p)):]
                            dst = osjoin(D,h)
                            src = osjoin(D,j)
                            logger.warning('rename %r to %r',src,dst)
                            os.rename(src, dst)
            else:
                raise RuntimeError('')
    elif prefix == 'delete':
        L = metadata.get_languages()
        if langchoice_ in L:
            del L[L.index(langchoice_)]
            set_lang( '\n'.join(L)  + '\n' )
            redirectlang_ = L[0]
            for j in os.listdir(D):
                if j[:4] in ('blob','view') and j[5:8] == langchoice_  and j[-1] != '~':
                    src = osjoin(D,j)
                    dst = src + '~disable~'
                    logger.debug('disable by renaming %r to %r',src,dst)
                    os.rename(src, dst)
        else:
            logger.warning(' lang %r not in %r',langchoice_,L)
    else:
        logmessage(messages.ERROR, 'Unimplemented %r %r'%(prefix,langchoice_))
    if prefix == 'translate' and settings.AUTO_MUL and \
       'mul' not in L and set(L) == set(coldoc.get_languages()):
        metadata.refresh_from_db()
        return postlang_no_http(logmessage, metadata, 'multlang', lang_, ext_ , langchoice_ )
    ColDoc.utils.recreate_symlinks(metadata, blobs_dir)
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + \
                    '?lang=%s&ext=%s'%(redirectlang_,ext_) )


def __allowed_image_mimetypes(ext=None):
    " `ext` is an extension to add to the list `ColDoc.config.ColDoc_show_as_image`"
    ll = list(ColDoc.config.ColDoc_show_as_image)
    if ext and ext not in ll:
        logger.warning('Extension %r is not in ColDoc.config.ColDoc_show_as_image', ext)
        ll.append(ext)
    m=[]
    for j in ll:
        if j in mimetypes.types_map:
            a = mimetypes.types_map.get(j)
            if a not in m:
                m.append(a)
        else:
            logger.error('Extension %r is not in mimetypes.types_map', j)
    return ll,m

@decorator_url()
def postupload(request, NICK, UUID, coldoc, coldoc_dir, blobs_dir, metadata, **k):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    form=BlobUploadForm(data=request.POST, files=request.FILES)
    #
    if not form.is_valid():
        a = "Invalid form: "+repr(form.errors)
        return HttpResponse(a,status=http.HTTPStatus.BAD_REQUEST)
    uuid = UUID
    uuid_dir = uuid_to_dir(uuid)
    #    
    E = metadata.get('extension')
    #
    try:
        os.unlink(osjoin(blobs_dir,uuid_dir,'.check_ok'))
    except OSError:
        pass
    #
    env = metadata.environ
    file_ = form.cleaned_data['file']
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    assert UUID == uuid_ and NICK == nick_
    assert lang_re.match(lang_)
    assert slugp_re.match(ext_)
    #
    if ext_ and not ( ext_ in E or ext_ in ColDoc.config.ColDoc_show_as_image):
        raise SuspiciousOperation()
    #
    allowed_ext , allowed_mime = __allowed_image_mimetypes(ext_ if ext_ else None)
    #
    f = file_._name
    newext = os.path.splitext(f)[1]
    if newext == '.jpg' :
        newext = '.jpeg'
    if  newext not in allowed_ext:
        messages.add_message(request,messages.ERROR,
                             _('File uploaded has extension of %(this)r instead of one of: %(that)r') %
                             {'this': newext , 'that': allowed_ext})
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    if file_.content_type not in allowed_mime:
        messages.add_message(request,messages.ERROR,
                             _('File uploaded is %(this)r instead of one of: %(that)r') %
                             {'this': file_.content_type , 'that': allowed_mime})
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    l = ('_'+lang_) if lang_ else ''
    D = os.path.join(blobs_dir, uuid_dir)
    F = os.path.join(D, 'blob' + l + newext)
    #
    try:
        T = tempfile.NamedTemporaryFile(dir=D, prefix='tmp_upload_')
        with open(T.name, 'wb') as destination:
            for chunk in file_.chunks():
                destination.write(chunk)
    except:
        logger.exception('failed receiving file %r',F)
        messages.add_message(request,messages.ERROR, _('File upload failed'))
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    if magic:
        a = magic.from_file(T.name, mime=True)
        if a not in allowed_mime:
                messages.add_message(request,messages.ERROR,
                             _('File uploaded is %(this)r instead of one of: %(that)r') %
                             {'this': a , 'that': allowed_mime})
                return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
        if a != file_.content_type:
            messages.add_message(request,messages.WARNING,
                             _('File uploaded is %(this)r instead of %(that)r') %
                             {'this': a , 'that': file_.content_type})
    #
    os.rename(T.name, F)
    T.delete = False
    #
    if newext not in E:
        metadata.add('extension',newext)
    metadata.blob_modification_time_update()
    metadata.save()
    #
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,newext))


def  __relatex_msg(res, all_messages):
    for thelang in res:
        if res[thelang]:
            a = _('Compilation of LaTeX succeded.') + '(%r)' % thelang
            all_messages.append( (messages.INFO, a) )
        else:
            a = _('Compilation of LaTeX failed') + '(%r)' % thelang
            all_messages.append( (messages.WARNING, a) )

def __relatex_new_msg(ret, all_messages):
    ret = all(ret.values())
    if ret:
        a = _('Compilation of new blob succeded')
        all_messages.append((messages.INFO, a))
    else:
        a = _('Compilation of new blob failed')
        all_messages.append((messages.WARNING, a))

def normalize(coldoc_dir, blobs_dir, metadata, blob, filters):
    if not blob.strip():
        return '\n'
    b = blob.splitlines()
    while b and not b[-1].strip():
        b.pop()
    if not b:
        return '\n'
    while b and not b[0].strip():
        b.pop(0)
    if not b:
        return '\n'
    b = [a.rstrip() for a in b]
    blob = '\n'.join(b) + '\n'
    #
    filename = '%s / %s' %(metadata.coldoc.nickname, metadata.uuid)
    #
    from ColDoc.latex import prepare_options_for_latex
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, metadata.coldoc)
    #
    errors = []
    token_filters = []
    squash_helper = []
    for name, fun in filters:
        if name.startswith('filter'):
            if name == "filter_math_to_unicode":
                f = osjoin(coldoc_dir, 'math_to_unicode.json')
                if os.path.isfile(f):
                    with open(f) as f_:
                        try:    
                            d = json.load(f_)
                        except:
                            logger.exception('while loading %r',f)
                        else:
                            fun = functools.partial(fun,update=d)
            token_filters.append(fun)
        if name.startswith('squash'):
            squash_helper.append(fun)
    if token_filters:
        helper = transform.squash_helper_stack
        out = io.StringIO()
        inp = io.StringIO(blob)
        inp.name = filename
        helper = transform.squash_latex(inp, out, options, helper, token_filters, errors)
        if helper == transform.squash_helper_token2unicode() :
            blob = transform.unsquash_unicode2token(out.getvalue(), helper)
        else:
            blob = out.getvalue()
    for helper in squash_helper:
        out = io.StringIO()
        inp = io.StringIO(blob)
        inp.name = filename
        helper = transform.squash_latex(inp, out, options, helper, errors)
        if isinstance(helper, transform.squash_helper_token2unicode) :
            blob = transform.unsquash_unicode2token(out.getvalue(), helper)
        else:
            blob = out.getvalue()
    return blob, errors

@decorator_url(ajax_actions = ('compile_no_reload', 'save_no_reload', 'normalize' ))
def postedit(request, NICK, UUID, coldoc, metadata, coldoc_dir, blobs_dir, uuid_dir, ajax_actions, do_lock, **k):
    #
    actions = 'compile', 'compile_no_reload', 'save', 'save_no_reload', 'normalize', 'revert'
    s = sum (int( a in request.POST ) for a in actions)
    assert 1 == s, request.POST.keys()
    the_action = [a for a in actions if a in request.POST].pop()
    #
    form=BlobEditForm(request.POST)
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    env = metadata.environ
    ## https://docs.djangoproject.com/en/dev/topics/forms/
    a = teh.list_allowed_choices(env)
    form.fields['split_environment'].choices = a
    if not a:
        form.fields['split_environment'].required = False
    #
    if not form.is_valid():
        a = "Invalid form: "+repr(form.errors)
        if the_action in ajax_actions:
            return JsonResponse({"message":json.dumps(a)})
        return HttpResponse(a,status=http.HTTPStatus.BAD_REQUEST)
    prologue = form.cleaned_data['prologue']
    shortprologue = form.cleaned_data['shortprologue']
    # convert to UNIX line ending 
    blobcontent  = re.sub("\r\n", '\n',  form.cleaned_data['blobcontent'] )
    if blobcontent and blobcontent[-1] != '\n':
        blobcontent += '\n'
    blobeditarea = re.sub("\r\n", '\n',  form.cleaned_data['BlobEditTextarea'] )
    if blobeditarea and blobeditarea[-1] != '\n':
        blobeditarea += '\n'
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    file_md5 = form.cleaned_data['file_md5']
    split_selection_ = form.cleaned_data['split_selection']
    split_environment_ = form.cleaned_data['split_environment']
    selection_start_ = json.loads(form.cleaned_data['selection_start'])
    selection_end_ = json.loads(form.cleaned_data['selection_end'])
    # CodeMirror returns  {line, ch}
    if isinstance(selection_start_, dict):
        line , ch = selection_start_['line'] , selection_start_['ch']
        form.cleaned_data['selection_start'] = selection_start_ =  ColDoc.utils.text_linechar2pos(blobeditarea, line, ch)
    if isinstance(selection_end_, dict):
        line , ch = selection_end_['line'] , selection_end_['ch']
        form.cleaned_data['selection_end']  = selection_end_ = ColDoc.utils.text_linechar2pos(blobeditarea, line, ch)
    split_add_beginend_ = form.cleaned_data['split_add_beginend']
    assert UUID == uuid_ and NICK == nick_
    assert lang_re.match(lang_)
    assert slugp_re.match(ext_)
    #
    if split_environment_ == 'graphic_file':
        c_lang = 'zxx'
    elif split_environment_ in ( 'usepackage' , 'bibliography' ):
        c_lang = 'und'
    else:
        c_lang = lang_
    #
    filename, uuid, metadata, lang, ext = \
        ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                 metadata = metadata,
                                 ext = ext_, lang = lang_, 
                                 metadata_class=DMetadata, coldoc=NICK)
    assert lang == lang_
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    can_change_blob = request.user.has_perm('UUID.change_blob')
    can_add_blob = request.user.has_perm('ColDocApp.add_blob')
    if not can_change_blob and not can_add_blob:
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    if split_selection_ and not can_add_blob:
        logger.error('Hacking attempt %r',request.META)
        #messages.add_message(request,messages.WARNING,'No permission to split selection')
        #split_selection_ = False
        raise SuspiciousOperation("Permission denied (add_blob)")
    #
    real_file_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    real_blobcontent = open(filename).read()
    if real_blobcontent and real_blobcontent[-1] != '\n':
            real_blobcontent += '\n'
    #
    if file_md5 != real_file_md5 and the_action.startswith('compile') :
        a = _("The file was changed on disk: compile aborted. Check the diff.")
        messages.add_message(request, messages.ERROR, a)
        if the_action in ajax_actions:
            H = difflib.HtmlDiff()
            blobdiff = H.make_table(open(filename).readlines(),
                                blobeditarea.splitlines(keepends=True),
                                _('Current'),_('Your version'), True)
            message = render_to_string(template_name="messages.html", request=request)
            return JsonResponse({'blob_md5': real_file_md5, 'uncompiled': 1,
                                'blobdiff':json.dumps(blobdiff),
                                'alert':json.dumps(str(a)),
                                "message":json.dumps(str(message)),
                                })
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')
    #
    try:
        os.unlink(osjoin(os.path.dirname(filename),'.check_ok'))
    except OSError:
        pass
    #
    normalize_errors = []
    if 'normalize' == the_action:
        filters = []
        for name, label, help, val, fun in transform.get_latex_filters():
            if form.cleaned_data[name]:
                filters.append((name, fun))
        blobeditarea, normalize_errors = normalize(coldoc_dir, blobs_dir, metadata, blobeditarea, filters)
        ## no these are not propagated thru json below
        #for s,a in normalize_errors:
        #    messages.add_message(request,messages.ERROR, gettext(s) % a)
    #
    weird_prologue = []
    if 'revert' != the_action:
        # put back prologue in place
        blobcontent, newprologue, sources , a, displacement = _put_back_prologue(prologue, blobeditarea, env, UUID)
        weird_prologue.extend(a)
        form.cleaned_data['blobcontent'] = blobcontent
        # some checks
        if split_selection_:
            if shortprologue is None:
                weird_prologue.append(_('Cannot split material when there are internal errors'))
                split_selection_ = False
            elif weird_prologue:
                weird_prologue.append(_('Cannot split material when there are header errors'))
                split_selection_ = False
            elif shortprologue and not blobeditarea.startswith(shortprologue + '\n'):
                weird_prologue.append(_('Sorry, cannot split material when the first line was changed'))
                split_selection_ = False
            else:
                selection_start_  = max(selection_start_ + displacement, 0)
                selection_end_    = max(selection_end_ + displacement, selection_end_)
    #
    else: # 'revert' in request.POST:
        blobcontent = real_blobcontent
        shortprologue, prologue, blobeditarea, warnings = __extract_prologue(blobcontent, UUID, env, metadata.optarg)
        form.cleaned_data.update({
            'BlobEditTextarea':  blobeditarea,
            'prologue' : prologue,
            'shortprologue' : shortprologue,
            'blobcontent' : blobcontent,
            })
        file_md5 = form.cleaned_data['file_md5'] = real_file_md5
        sources = newprologue = None
    #
    # save state of edit form
    uncompiled = 0
    if can_change_blob:
        user_id = str(request.user.id)
        file_editstate = filename[:-4] + '_' + user_id + '_editstate.json'
        uncompiled = int(real_blobcontent != blobcontent)
        with open(file_editstate,'w') as f_:
            json.dump(form.cleaned_data, f_)
    #
    ch__ = _("The file was changed on disk: check the diff")
    #
    if the_action in ('save_no_reload' , 'normalize' , 'revert'):
        H = difflib.HtmlDiff()
        blobdiff = H.make_table(open(filename).readlines(),
                                blobcontent.splitlines(keepends=True),
                                _('Current'),_('Your version'), True)
        if ( file_md5 != real_file_md5 ):
            messages.add_message(request, messages.WARNING, ch__ )
        for wp in weird_prologue:
            messages.add_message(request, messages.WARNING, wp )
        for string_,argument_ in normalize_errors:
            messages.add_message(request, messages.WARNING, _(string_) % argument_ )
        message = render_to_string(template_name="messages.html", request=request)
        D = {'blob_md5': real_file_md5, 'uncompiled' : uncompiled,
                             'blobdiff':json.dumps(blobdiff),
                             "message":json.dumps(str(message)),
                             'blobeditarea' : json.dumps(blobeditarea),}
        if ( file_md5 != real_file_md5 ):
            D['alert'] = json.dumps(str(ch__ ))
        return JsonResponse(D)
    # if we reach here we know that this is empty
    del  normalize_errors
    if 'save' == the_action:
        if ( file_md5 != real_file_md5 ):
            messages.add_message(request,messages.WARNING, ch__)
        for wp in  weird_prologue:
            messages.add_message(request,messages.WARNING, wp)
        messages.add_message(request,messages.INFO,'Saved')
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')
    # diff
    file_lines_before = open(filename).readlines()
    shutil.copy(filename, filename+'~~')
    #
    uuid_as_html = '<a href="%s">%s</a>' %(
        request.build_absolute_uri(django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':uuid})), uuid)
    # write new content
    if can_change_blob:
        with open(filename,'w') as f_:
            f_.write(blobcontent)
        metadata.blob_modification_time_update()
        if sources is not None:
            metadata.optarg = json.dumps(sources)
        metadata.save()
    else:
        pass # may want to check that form was not changed...
    # TODO we should have two copies, for html and for text form of each message
    # this is a list of pairs (level, message)
    all_messages = [ (messages.WARNING, a) for a in weird_prologue]
    del weird_prologue
    #
    do_fork = fork_class_default().can_fork()
    fork1 = fork2 = None
    #
    from ColDoc.latex import environments_we_wont_latex
    from ColDoc.utils import reparse_blob
    #
    reparse_options = {'unicode_to_latex' : load_unicode_to_latex(coldoc_dir)}
    load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
    #
    if split_selection_:
        from helper import add_blob
        addsuccess, addmessage, addnew_uuid = \
            add_blob(logger, request.user, settings.COLDOC_SITE_ROOT, nick_, uuid_, 
                 split_environment_, lang_, c_lang, selection_start_ , selection_end_, split_add_beginend_)
        if addsuccess:
            # len of \input{UUID/0/1/1/blob_eng.tex} , plus optionally begin..end
            selection_end_  = selection_start_ + 32 
            if split_environment_[:2] == 'E_' and split_add_beginend_:
                selection_end_ += 10 + 2 * len(split_environment_)
            #
            new_uuid_as_html = '<a href="%s">%s</a>' %(
                request.build_absolute_uri(django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':addnew_uuid})),
                addnew_uuid)
            addmessage = _("Created blob with UUID %(newuuid)s, please edit %(olduuid)s to properly input it (a stub \\input was inserted for your convenience)") %\
                          {'newuuid':new_uuid_as_html, 'olduuid':uuid_as_html}
            all_messages.append( (messages.INFO, addmessage) )
            addmetadata = DMetadata.load_by_uuid(uuid=addnew_uuid,coldoc=coldoc)
            add_extension = addmetadata.get('extension')
        else:
            add_extension = []
            all_messages.append( (messages.WARNING,addmessage) )
        if  '.tex' in add_extension:
            addfilename, adduuid, addmetadata, addlang, addext = \
                ColDoc.utils.choose_blob(uuid=addnew_uuid, blobs_dir = blobs_dir,
                                         ext = ext_, lang = lang_,
                                         metadata_class=DMetadata, coldoc=NICK)
            # parse it for metadata
            def warn(msg, args):
                msg =  _(msg) % args
                all_messages.append( ( messages.INFO, _('Metadata change in new blob') + ': ' + msg) )
            reparse_blob(addfilename, addmetadata, lang, blobs_dir, warn, load_uuid=load_uuid, options=reparse_options)
            # compile it
            if do_fork:
                fork2 = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, addmetadata, fork=True)
            else:
                ret = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, addmetadata)
                __relatex_new_msg(ret, all_messages)
    #
    # parse it to refresh metadata (after splitting)
    def warn(msg, args):
        msg = _(msg) % args
        all_messages.append( (messages.INFO,  _('Metadata change in blob') + ': ' + msg) )
    reparse_blob(filename, metadata, lang, blobs_dir, warn, load_uuid=load_uuid, options=reparse_options)
    #
    if ext_ in  ('.tex', '.bib'):
        gen_lang_metadata(metadata, blobs_dir, coldoc.get_languages())
        if do_fork:
            fork1 = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, metadata, fork=True)
            a = _('Compilation of LaTeX scheduled.')
            all_messages.append( (messages.INFO, a))
        else:
            ret = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, metadata)
            __relatex_msg(ret, all_messages)
    logger.info('ip=%r user=%r coldoc=%r uuid=%r ',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
    email_to = _interested_emails(coldoc,metadata)
    #
    if not email_to:
        logger.warning('No author has a validated email %r', metadata)
    else:
        a = _("User '%s' changed %s - %s - %s") % (request.user , metadata.coldoc.nickname, metadata.uuid, lang_)
        r = get_email_for_user(request.user)
        if r is not None: r = [r]
        E = EmailMultiAlternatives(subject = a,
                         from_email = settings.DEFAULT_FROM_EMAIL,
                         to= email_to,
                         reply_to = r)
        # html version
        H = difflib.HtmlDiff()
        file_lines_after = open(filename).readlines()
        blobdiff = H.make_file(file_lines_before,
                               file_lines_after,
                               _('Previous'),_('Current'), True)
        try:
            j  = blobdiff.index('<body>') + 6
            l = len(all_messages)
            a = ( '<li>{}\n' * l ).format(* map(str,  [ a[1] for a in all_messages]  ))
            blobdiff = blobdiff[:j] + '<ul>\n' + a + \
                '</ul>\n<h1>' + _('File differences for') + ' ' + uuid_as_html + '</h1>\n' + blobdiff[j:]
        except:
            logger.exception('While preparing ')
        else:
            E.attach_alternative(blobdiff, 'text/html')
        # text version
        message = ''
        try:
            l = len(all_messages)
            a = [ html2text(str(a[1])) for a in all_messages ]
            message = ('*) {}\n' * l).format(*a)
        except:
            logger.exception('While preparing ')
        P = subprocess.run(['diff', '-u', filename + '~~', filename, ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False, universal_newlines=True )
        message += '\n*** File differences ***\n\n' +  P.stdout
        E.attach_alternative(message, 'text/plain')
        # send it
        try:
            E.send()
        except:
            logger.exception('email failed')
    # re-save form data, to account for possible splitting
    if can_change_blob:
        D = {}
        D['file_md5'] = hashlib.md5(open(filename,'rb').read()).hexdigest()
        D['split_selection'] = False
        D['selection_start'] = selection_start_
        D['selection_end'] = selection_end_
        D['lang'] = lang
        D['UUID'] = uuid
        D['ext'] = ext
        with open(file_editstate,'w') as f_:
            json.dump(D, f_)
    #
    if do_fork:
        a = 'compilation_in_progress_' + metadata.uuid
        request.session[a] = base64.a85encode(pickle.dumps((fork1,fork2))).decode('ascii')
        request.session.save()
    #
    if the_action == 'compile_no_reload' :
        H = difflib.HtmlDiff()
        blobdiff = H.make_table(file_lines_before,
                               file_lines_after,
                               _('Previous'),_('Current'), True)
        #
        real_file_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
        blobcontent = open(filename).read()
        if blobcontent and blobcontent[-1] != '\n' :
            blobcontent += '\n'
        # the first line contains the \uuid command or the \section{}\uuid{}
        shortprologue, prologue, blobeditdata, warnings = __extract_prologue(blobcontent, UUID, env, metadata.optarg)
        #
        alert='\n'.join( [ html2text(str(v[1])) for v in all_messages if v[0] >= messages.WARNING ] )
        for a,b in all_messages:
            messages.add_message(request, a, b)
        message = render_to_string(template_name="messages.html", request=request)
        #
        parent_metadata, downlink, uplink, leftlink, rightlink = index_arrows(metadata)
        arrows = render_to_string(template_name="UUID_arrows.html",
                                  context = locals(),
                                  request=request)
        #
        z =    {'uncompiled' : 0, 'blob_md5': real_file_md5,
                'blobeditarea' : json.dumps(blobeditdata),
                'blobdiff' : json.dumps(blobdiff),
                "alert"  : json.dumps(str(alert)),
                "arrows_html"  : json.dumps(str(arrows)),
                "message"  : json.dumps(str(message)),
                }
        if not do_fork:
            views = __prepare_views(metadata, blobs_dir)
            z[ "viewarea" ] = json.dumps(views)
        return JsonResponse(z)
    for a,b in all_messages:
        messages.add_message(request, a, b)
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')

def __prepare_views(metadata, blobs_dir):
    uuid_dir = uuid_to_dir(metadata.uuid)
    Blangs = metadata.get_languages()
    CDlangs = metadata.coldoc.get_languages()
    d = os.path.join( blobs_dir, uuid_dir)
    # fixme this works fine only for TeX to HTML
    views = []
    children = metadata.get('child_uuid')
    url = django.urls.reverse('UUID:index', kwargs={'NICK':metadata.coldoc.nickname,'UUID':'000'})
    for ll in  set(Blangs + CDlangs):
        f = os.path.join(d,'view_' + ll + '_html' , 'index.html')
        if os.path.isfile(f):
            h = open(f).read()
            h = _html_replace(h, url[:-4], metadata.uuid, ll, True, children)
            views.append( (ll,h) )
    return views


##@csrf_exempt
def ajax_views(request, NICK, UUID):
    if request.method != 'POST' :
        raise SuspiciousOperation('!!!')
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
    load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
    request.user.associate_coldoc_blob_for_has_perm(coldoc, metadata)
    anon_dir  = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
    can_view_blob = request.user.has_perm('UUID.view_blob')
    if not can_view_blob:
        raise SuspiciousOperation("Permission denied")
    #
    all_messages = []
    a = 'compilation_in_progress_' + metadata.uuid
    if a in  request.session:
        fork1 = fork2 = None
        try:
            with transaction.atomic():
                b =  request.session.pop(a)
                request.session.save()
            if b is not None:
                fork1,fork2 = pickle.loads(base64.a85decode(b))
        #
            if fork1 is not None:
                res1 = fork1.wait()
                __relatex_msg(res1, all_messages)
            #
            if fork2 is not None:
                res2 = fork1.wait()
                __relatex_new_msg(res2, all_messages)
        except RuntimeWarning as e:
            logger.warning(str(e))
            all_messages.append( (messages.WARNING, py_html_escape(str(e))  ) )
        except Exception as e:
            logger.exception('while managing jobs')
            all_messages.append( (messages.ERROR, py_html_escape(str(e))  ) )
    #
    views = __prepare_views(metadata, blobs_dir)
    alert='\n'.join( [ html2text(str(v[1])) for v in all_messages if v[0] >= messages.WARNING ] )
    for a,b in all_messages:
        messages.add_message(request, a, b)
    message = render_to_string(template_name="messages.html", request=request)
    #
    metadata.refresh_from_db()
    coldoc.refresh_from_db()
    a = metadata.latex_return_codes if UUID != metadata.coldoc.root_uuid else metadata.coldoc.latex_return_codes
    latex_error_logs = convert_latex_return_codes(a, NICK, UUID)
    if latex_error_logs:
        latex_error_logs = latex_error_fix_line_numbers(blobs_dir, anon_dir, metadata.uuid, latex_error_logs, load_uuid)
        latex_errors_html = render_to_string(template_name="latex_error_logs.html",
                                             context = {"latex_error_logs":latex_error_logs,
                                                        'NICK':coldoc.nickname,
                                                        },
                                             request=request )
    else:
        latex_errors_html = ''
    #
    parent_metadata, downlink, uplink, leftlink, rightlink = index_arrows(metadata)
    arrows = render_to_string(template_name="UUID_arrows.html",
                              context = locals(),
                              request=request)
    #
    return JsonResponse( {"message"  : json.dumps(str(message)),
                          "latex_errors_html" : json.dumps(str(latex_errors_html)),
                          "arrows_html" : json.dumps(str(arrows)),
                          "alert"  : json.dumps(str(alert)),
                          "viewarea" : json.dumps(views),  })

@decorator_url()
def postmetadataedit(request, NICK, UUID, coldoc, coldoc_dir, blobs_dir, uuid_dir, metadata, **k):
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    #
    uuid = UUID
    uuid_dir = uuid_to_dir(uuid)
    #
    try:
        os.unlink(osjoin(blobs_dir,uuid_dir,'.check_ok'))
    except OSError:
        pass
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    if not request.user.has_perm('UUID.change_dmetadata'):
        logger.error('Hacking attempt',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    baF = metadata.backup_filename()
    before = open(baF).readlines()
    shutil.copy(baF, baF+'~~')
    #
    form=MetadataForm(request.POST, instance=metadata)
    #
    j = metadata.get('parent_uuid')
    if j:
        parent_metadata = DMetadata.load_by_uuid(j[0], metadata.coldoc)
        choices = teh.list_allowed_choices(parent_metadata.environ)
    else:
        choices = [('main_file','main_file',)] # == teh.list_allowed_choices(False)
    # useless
    form.fields['environ'].choices = choices
    # useful
    form.fields['environ'].widget.choices = choices
    #
    if not form.is_valid():
        return HttpResponse("Invalid form: "+repr(form.errors),status=http.HTTPStatus.BAD_REQUEST)
    #
    uuid_ = form.cleaned_data['uuid_']
    lang_ = form.cleaned_data['lang_']
    ext_ = form.cleaned_data['ext_']
    assert lang_re.match(lang_)
    assert slugp_re.match(ext_)
    environ_ = form.cleaned_data['environ']
    if uuid != uuid_ :
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation('UUID Mismatch')
    if ext_ not in metadata.get('extension') :
        messages.add_message(request,messages.WARNING, _('Internal problem, check the metadata again %r != %r') %\
                             ([ext_], metadata.extension))
    #
    form.save()
    messages.add_message(request,messages.INFO,_('Changes saved'))
    #
    from ColDoc.latex import environments_we_wont_latex
    if ext_ == '.tex':
        gen_lang_metadata(metadata, blobs_dir, coldoc.get_languages())
        m = []
        res = _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, metadata)
        __relatex_msg(res, m)
        for a,b in m: messages.add_message(request, a,b )
    logger.info('ip=%r user=%r coldoc=%r uuid=%r ',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
    #
    email_to = _interested_emails(coldoc,metadata)
    if not email_to:
        logger.warning('No author has a validated email %r', metadata)
    else:
        a = _("User '%s' changed metadata in %s - %s") % (request.user , metadata.coldoc.nickname, metadata.uuid)
        r = get_email_for_user(request.user)
        P = subprocess.run(['diff', '-u', baF+'~~', baF, ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False, universal_newlines=True )
        message = P.stdout
        after = open(metadata.backup_filename()).readlines()
        H = difflib.HtmlDiff()
        html_message = H.make_file(before, after, _('Orig'),_('New'), True)
        if r is not None: r = [r]
        E = EmailMultiAlternatives(subject = a, 
                         from_email = settings.DEFAULT_FROM_EMAIL,
                         to= email_to, reply_to = r)
        E.attach_alternative(message, 'text/plain')
        E.attach_alternative(html_message, 'text/html')
        try:
            E.send()
        except:
            logger.exception('email failed')
    #
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID})  + '?lang=%s&ext=%s'%(lang_,ext_))

def _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc, url=None):
    from ColDoc.latex import prepare_options_for_latex
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, coldoc)
    #
    # used for PDF
    if url is None and request is not None:
        url = django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':'000'})[:-4]
        url = request.build_absolute_uri(url)
    if url is not None:
        options['url_UUID'] = url
    #
    from ColDocDjango.transform import squash_helper_ref
    load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
    options["squash_helper"] = functools.partial(squash_helper_ref, coldoc=coldoc, load_uuid=load_uuid)
    options['metadata_class'] = DMetadata
    # used by the deduping mechanism
    options['coldoc_site_root']  = settings.COLDOC_SITE_ROOT
    options['dedup_root'] = settings.DEDUP_ROOT
    options['dedup_url'] = settings.DEDUP_URL
    #
    options['html_to_text_callback'] =  functools.partial(text_catalog.update_text_catalog_for_uuid, coldoc=coldoc)
    #
    from ColDocDjango.utils import parse_for_labels_callback
    options['callback_after_blob_compiled'] = functools.partial(parse_for_labels_callback,  coldoc_dir=coldoc_dir, coldoc=coldoc)
    #
    options['unicode_to_latex'] = load_unicode_to_latex(coldoc_dir)
    # floating preamble
    try:
        m = DMetadata.objects.filter(original_filename = '/preamble.tex').filter(coldoc = coldoc).get()
        preamble_dir = ColDoc.utils.uuid_to_dir(m.uuid, blobs_dir)
        options['preamble'] = osjoin(preamble_dir, 'blob_{lang}.tex')
    except:
        logger.exception('While looking for   "/preamble.tex" ')
    return options

def _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, metadata, fork=False):
    options = _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc)
    from ColDoc import latex
    if not fork:
        return latex.latex_uuid(blobs_dir, metadata=metadata, options=options)
    else:
        fork = fork_class_default()
        if settings.CLOSE_CONNECTION_ON_FORK and fork_class_default.fork_type in ('simple',) :
            from django import db
            db.close_old_connections()
        fork.run(latex.latex_uuid, blobs_dir, metadata=metadata, options=options,
                 forked=fork.use_fork, fork_class=fork_class_default)
        return fork

##############################################################

def _html_replace_not_bs(html, url, uuid, lang, expandbuttons=True, children = [], highlight=None):
    html = html.replace(ColDoc.config.ColDoc_url_placeholder,url)
    # help plasTeX find its images
    html = html.replace('src="images/','src="html/images/')
    #
    return html


def _html_replace_bs(html, url, uuid, lang, expandbuttons=True, children = [], highlight=None):
    ids = 0
    assert isinstance(lang,str)
    idp = 'UUID_lSa2q_' + uuid + '_' + lang + '_' 
    if url[-1] != '/':
        url += '/'
    children = set(children)
    CP = ColDoc.config.ColDoc_url_placeholder
    lCP = len(CP)
    skipuuid = CP + uuid
    soup = BeautifulSoup(html, features="html.parser")
    for a in soup.findAll('a'):
        ids += 1
        if 'href' in a.attrs and a['href'].startswith(CP):
            thisuuid = a['href'][lCP:]
            if not expandbuttons or a['href'].startswith(skipuuid) :
                a['href'] = url + thisuuid
                continue
            identA = idp + 'A' + str(ids)
            identB = idp + 'B' + str(ids)
            identC = idp + 'C' + str(ids)
            identD = idp + 'D' + str(ids)
            identP = idp + 'P' + str(ids)
            identS = idp + 'S' + str(ids)
            # link
            a['href'] = h = url + thisuuid
            # parent
            p = a.parent
            # set or get ids
            if 'id'  in p.attrs:
                identP = p['id']
            else:
                p['id'] = identP
            if 'id'  in a.attrs:
                identA = a['id']
            else:
                a['id'] = identA
            #
            c_ = 'success' if thisuuid in children else 'dark'
            # span
            s = soup.new_tag('span', id=identS)
            s['class'] = "border border-" + c_ + (' bg-warning' if (highlight == thisuuid) else '' )
            a = a.replaceWith(s)
            s.append(a)
            #
            args = (h+'/html?lang=' + lang + ',', identS, identA, identB, identC, identD)
            # button
            r = "html_retrieve_substitute('%s','%s','%s','%s','%s','%s')" % args
            b = soup.new_tag('button', id=identB, onClick=r)
            b.string='↺'
            b['class'] = "btn btn-outline-" + c_ + " btn-sm"
            s.append(b)
            # cancel button
            r = "html_hide_substitute('%s','%s','%s','%s','%s','%s')" % args
            c = soup.new_tag('button', id=identC, onClick=r)
            c.string='↻'
            c['class'] = "btn btn-outline-warning btn-sm position-absolute top-0 end-0"
            c['style'] = "display: none;"
            s.append(c)
            # div
            d = soup.new_tag('span', id=identD)
            d['class'] = "border border-" + c_ + " m-2 p-2 position-relative"
            d['style'] = "display: none;"
            s.append(d)
    #
    if expandbuttons:
        for a in soup.findAll('img'):
            a['src'] = url + uuid + '/html/' + a['src']
    return str(soup)

if BeautifulSoup is None:
    _html_replace = _html_replace_not_bs
else:
    _html_replace = _html_replace_bs


###############################################################

@xframe_options_sameorigin
def pdf(request, NICK, UUID):
    return view_(request, NICK, UUID, '.pdf', 'application/pdf')

@xframe_options_sameorigin
def txt(request, NICK, UUID):
    return view_(request, NICK, UUID, '_html.txt', 'text/plain')


@xframe_options_sameorigin
def html(request, NICK, UUID, subpath=None):
    return view_(request, NICK, UUID, '_html', None, subpath, expandbuttons = True)

@xframe_options_sameorigin
def show(request, NICK, UUID):
    return view_(request, NICK, UUID, None, None, None, prefix='blob')

def log(request, NICK, UUID):
    return view_(request, NICK, UUID, None, None, None, prefix='log')


def view_(request, NICK, UUID, _view_ext, _content_type, subpath = None, prefix='view', expandbuttons = True):
    " UUID=True means UUID=root_uuid of coldoc "
    r = view_mul(request, NICK, UUID, _view_ext, _content_type, subpath, prefix, expandbuttons )
    # some error
    if not isinstance(r,tuple):
        return r
    #
    download='download' in request.GET
    #
    n, access, _content_type, _content_encoding, _view_ext, coldoc, uuid, lang, child_uuid = r
    #
    try:
        if _content_type == 'text/html':
            f = open(n).read()
            a = django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname, 'UUID':'001'})
            f = _html_replace(f, a[:-4], uuid, lang, expandbuttons, child_uuid )
            response = HttpResponse(f, content_type=_content_type, charset=_content_encoding)
        elif _content_type.startswith('text/'):
            f = open(n)
            response = HttpResponse(f, content_type=_content_type, charset=_content_encoding)
        else:
            fsock = open(n,'rb')
            response = HttpResponse(fsock, content_type=_content_type)
    except FileNotFoundError:
        logger.warning('FileNotFoundError user=%r coldoc=%r uuid=%r ext=%r lang=%r',request.user.username,NICK,UUID,_view_ext,lang)
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID, lang, _view_ext),
                            status=http.HTTPStatus.NOT_FOUND)
    if download:
        response['Content-Disposition'] = "attachment; filename=ColDoc-%s%s" % (UUID,_view_ext)
    return response


def view_mul(request, NICK, UUID, _view_ext, _content_type, subpath = None, prefix='view', expandbuttons = True):
    " UUID=True means UUID=root_uuid of coldoc "
    #
    logger.debug('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r : entering',
                request.META.get('REMOTE_ADDR'), request.user.username,
                NICK,UUID,_view_ext,_content_type,subpath,prefix)
    # do not allow subpaths for non html
    assert _view_ext == '_html' or subpath is None
    assert _view_ext in ('_html','_html.txt','.pdf',None)
    assert prefix in ('main','view','blob','log')
    if not ( ( isinstance(NICK,str) and slug_re.match(NICK) )  or isinstance(NICK,DColDoc) ):
        raise SuspiciousOperation(repr(NICK))
    if not ( ( isinstance(UUID,str) and slug_re.match(UUID) ) or ( UUID is True) ) : raise SuspiciousOperation(repr(UUID))
    #
    if isinstance(NICK,DColDoc):
        coldoc = NICK
        NICK = coldoc.nickname
    else:
        try:
            coldoc = DColDoc.objects.filter(nickname = NICK).get()
        except DColDoc.DoesNotExist:
            return HttpResponse("No such ColDoc %r.\n" % (NICK,) , status=http.HTTPStatus.NOT_FOUND)
    #
    if UUID is True :
        UUID = coldoc.root_uuid
    #
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            # TODO this is not shown
            messages.add_message(request, messages.WARNING,
                                 _("UUID was normalized from %(old)r to %(new)r)") %   {'old':UUID,'new':a})
        UUID = a
    except ValueError as e:
        return HttpResponse("Internal error for UUID %r : %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    #
    q = request.GET
    # used only for `show` view
    if _view_ext is None:
        if 'ext' in q:
            _view_ext = q['ext']
            if not slugp_re.match(_view_ext):
                raise SuspiciousOperation("Invalid ext %r in query." % (_view_ext,))
        else:
            return HttpResponse("must specify extension", status=http.HTTPStatus.NOT_FOUND)
    # used for main document logs, and cross checks
    access = q.get('access')
    if access not in (None, 'open', 'public', 'private', 'undefined'):
        return HttpResponse("Wrong access request", status=http.HTTPStatus.BAD_REQUEST)
    #
    if prefix == 'log' and  _view_ext not in ColDoc.config.ColDoc_allowed_logs:
        return HttpResponse("Permission denied (log)", status=http.HTTPStatus.UNAUTHORIZED)
    #
    # if user is editor, provide true access
    blobs_subdir = 'blobs'
    blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
    if prefix == 'main':
        request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
        if access in ('public','open') or not request.user.has_perm('UUID.view_view'):
            # users.user_has_perm() will grant `private` access to editors
            blobs_subdir = 'anon'
            blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
            if access == 'private':
                messages.add_message(request, messages.WARNING, _('Access to private document denied. Please login.'))
            access = 'public'
        else:
            access = 'private'
    #
    if not os.path.isdir(blobs_dir):
        return HttpResponse("No such ColDoc %r.\n" % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    #
    lang = q.get('lang')
    __redirect_other_lang(request,lang,_view_ext)
    if lang is not None and  not langc_re.match(lang):
            raise SuspiciousOperation("Invalid lang %r in query." % (lang,))
    if lang:
        lang, allow_lang_fallback = lang[:3],lang[3:]
    #for j in q:
    #    if j not in ('ext','lang'):
    #        messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
    #
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    accept_lang = ColDocDjango.utils.request_accept_language(accept, cookie)
    if lang:
        accept_lang[lang] = 3.0
    #
    try:
        uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                       blobs_dir = blobs_dir, coldoc = NICK,
                                                       metadata_class=DMetadata)
        #
        request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
        if not request.user.has_perm('UUID.view_view'):
            logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r: permission denied',
                        request.META.get('REMOTE_ADDR'), request.user.username,
                        NICK,UUID,_view_ext,_content_type,subpath,prefix)
            return HttpResponse("Permission denied (view)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        # at this point we know that 'UUID.view_view' is granted; will check 'UUID.view_blob'
        # later, so that for image files, access will be granted regardless of 'UUID.view_blob'
        if prefix=='log' and not request.user.has_perm('UUID.view_log'):
            logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r : permission denied',
                        request.META.get('REMOTE_ADDR'), request.user.username,
                        NICK,UUID,_view_ext,_content_type,subpath,prefix)
            return HttpResponse("Permission denied (log)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        #
        env = metadata.get('environ')[0]
        if env in ColDoc.latex.environments_we_wont_latex and _view_ext == '_html':
            return  HttpResponse('There is no %r for %r' % (_view_ext, env), content_type='text/plain')
        # TODO should serve using external server see
        #   https://stackoverflow.com/questions/2687957/django-serving-media-behind-custom-url
        #   
        n = None
        isdir = False
        Blangs = metadata.get_languages()
        if 'mul' in Blangs:
            Blangs = metadata.coldoc.get_languages()
        # FIXME having language '' or None is legacy, may be deleted
        langs = [lang] if (lang is not None) else []
        if lang is None or allow_lang_fallback:
            langs += ( Blangs + [None] )
        langs.sort(key = lambda x : accept_lang.get(x,0), reverse=True)
        pref_ = prefix
        # access to logs
        if  prefix == 'log' :
            if UUID == metadata.coldoc.root_uuid:
                pref_ = 'main'
                if access == 'public':
                    blobs_subdir = 'anon'
                    blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
            else:
                pref_ = 'view'
        #
        for l in langs:
            # FIXME having language '' or None is legacy, may be deleted
            assert l in (None,'') or slug_re.match(l)
            if l not in (None,''):
                _l = '_'+l
            else:
                _l = ''
            n = os.path.join(blobs_dir, uuid_dir, pref_ + _l + _view_ext)
            if subpath is not None:
                n = os.path.join(n,subpath)
            if os.path.isfile(n):
                break
            elif os.path.isdir(n) and os.path.isfile(n+'/index.html'):
                n+='/index.html'
                isdir=True
                break
            else:
                n = None
        lang = l
        if n is None:
            logger.warning('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r pref_=%r langs=%r blobs_subdir=%r : cannot find',
                        request.META.get('REMOTE_ADDR'), request.user.username,
                        NICK,UUID,_view_ext,_content_type,subpath, pref_, langs, blobs_subdir)
            return HttpResponse("Cannot find %s.....%s, subpath %r, for UUID %r , looking for languages in %r." %\
                                (pref_,_view_ext,subpath,UUID,langs),
                                content_type='text/plain', status=http.HTTPStatus.NOT_FOUND)
        # we assume that all text files are in DEFAULT_CHARSET that usually is utf-8
        _content_encoding = settings.DEFAULT_CHARSET
        if _content_type is None:
            if _view_ext in ColDoc.config.ColDoc_allowed_logs :
                _content_type = 'text/plain'
            else:
                _content_type , _content_encoding = mimetypes.guess_type(n)
        if _content_type is None and magic:
            _content_type = magic.from_file(n, mime=True)
        if _content_type is None  :
            _content_type = 'application/octet-stream'
        #
        if prefix=='blob' and not ( request.user.has_perm('UUID.view_blob') or is_image_blob(metadata, _content_type) ):
            logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r pref_=%r : permission denied',
                        request.META.get('REMOTE_ADDR'), request.user.username,
                        NICK,UUID,_view_ext,_content_type,subpath,pref_)
            return HttpResponse("Permission denied (blob)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        #
        logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r lang=%r pref_=%r blobs_subdir=%r : content served',
                    request.META.get('REMOTE_ADDR'), request.user.username,
                    NICK,UUID,_view_ext,_content_type,subpath,prefix,lang,pref_,blobs_subdir)
        #
        child_uuid = metadata.get('child_uuid')
        #
        return (n, access, _content_type, _content_encoding, _view_ext, coldoc, uuid, lang, child_uuid)
    #
    except FileNotFoundError:
        logger.warning('FileNotFoundError user=%r coldoc=%r uuid=%r ext=%r lang=%r',request.user.username,NICK,UUID,_view_ext,lang)
        return HttpResponse("Cannot find UUID %r with langs=%r , extension=%r." % (UUID,langs,_view_ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.exception(e)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e),
                            status=http.HTTPStatus.INTERNAL_SERVER_ERROR)


def get_access_icon(access):
    H = full_escape_lazy
    ACCESS_ICONS = {'open':    ('<img src="%s" style="height: 12pt"  data-toggle="tooltip" title="%s">' % \
                                (static('ColDoc/Open_Access_logo_PLoS_white.svg'),
                                 H(DMetadata.ACCESS_CHOICES[0][1]))), #
                    'public':  ('<span style="font-size: 12pt" data-toggle="tooltip" title="%s">%s</span>' %\
                                (H(DMetadata.ACCESS_CHOICES[1][1]),chr(0x1F513),)), # '🔓'
                    'private': ('<span style="font-size: 12pt" data-toggle="tooltip" title="%s">%s</span>' %\
                                (H(DMetadata.ACCESS_CHOICES[2][1]),chr(0x1F512),)), # '🔒'
                        }
    return ACCESS_ICONS[access]

def index_arrows(metadata, children = None):
    parent_metadata = parent_uuid = None
    if children is None:
        children = metadata.get('child_uuid')
    uplink = downlink = leftlink = rightlink = None
    UUID = metadata.uuid
    NICK = metadata.coldoc.nickname
    try:
        j = children
        if j:
            downlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[0]})
        j = metadata.get('parent_uuid')
        if j:
            parent_uuid = j[0]
            parent_metadata = DMetadata.load_by_uuid(parent_uuid, metadata.coldoc)
            uplink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':parent_uuid})
            uplink += '?highlight=' + UUID
        elif 'main_file' not in metadata.get('environ'):
            logger.warning('no parent for UUID %r',UUID)
    except:
        logger.exception('WHY?')
    if parent_metadata is not None:
        j = list(parent_metadata.get('child_uuid'))
        try:
            i = j.index(UUID)
            if i>0:
                leftlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i-1]})
            if i<len(j)-1:
                rightlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i+1]})
        except:
            logger.exception('problem finding siblings for UUID %r',UUID)
    return parent_metadata, downlink, uplink, leftlink, rightlink


diff_table_template = """
    <table class="diff" id="difflib_chg_%(prefix)s_top" >
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        %(header_row)s
        <tbody>
%(data_rows)s        </tbody>
    </table>"""


def index(request, NICK, UUID):
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID, accept_anon=True)
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    has_general_view_view = request.user.has_perm('UUID.view_view')
    anon_dir  = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
    global_blobs_dir = blobs_dir if has_general_view_view else anon_dir
    #
    logger.debug('ip=%r user=%r coldoc=%r uuid=%r : entering',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
    #
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            # https://docs.djangoproject.com/en/3.0/ref/contrib/messages/
            messages.add_message(request, messages.WARNING,
                                 "UUID was normalized from %r to %r"%(UUID,a))
        UUID = a
    except ValueError as e:
        return HttpResponse("Invalid UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.BAD_REQUEST)
    #
    uuid_dir = ColDoc.utils.uuid_to_dir(UUID, blobs_dir=blobs_dir)
    #
    q = request.GET
    ext = None
    if 'ext' in q:
        ext = q['ext']
        if not slugp_re.match(ext):
            raise SuspiciousOperation("Invalid ext %r in query." % (ext,))
    lang = q.get('lang')
    __redirect_other_lang(request,lang,ext)
    if lang is not None and not lang_re.match(lang):
            raise SuspiciousOperation("Invalid lang %r in query." % (lang,))
    highlight = q.get('highlight')
    if highlight is not None and not slug_re.match(highlight):
            raise SuspiciousOperation("Invalid highlight %r in query." % (highlight,))
    for j in q:
        if j not in ('ext','lang','highlight'):
            messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
            logger.warning( 'Ignored query %r'%(j,) )
    #
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    accept_lang = ColDocDjango.utils.request_accept_language(accept, cookie)
    try:
        blob_filename, uuid, metadata, blob_lang, blob_ext = \
            ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                     ext = ext, lang = lang,
                                     accept_lang = accept_lang,
                                     metadata_class=DMetadata, coldoc=NICK, prefix = 'edit')
        blob__dir = os.path.dirname(blob_filename)
    except FileNotFoundError:
        logger.warning('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: file not found',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID,lang,ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.exception('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: exception',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    try:
        view_filename, uuid, metadata, view_lang, view_ext = \
            ColDoc.utils.choose_blob(blobs_dir = blobs_dir,
                                     lang = lang if lang != 'mul' else None,
                                     accept_lang = accept_lang,
                                     metadata=metadata, prefix='view')
    except FileNotFoundError:
        view_filename = view_lang = view_ext = None
    except Exception as e:
        logger.exception('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: exception',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    #
    load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
    #
    Blangs = metadata.get_languages()
    CDlangs = coldoc.get_languages()
    #
    BLOB = os.path.basename(blob_filename)
    blob_md5 = hashlib.md5(open(blob_filename,'rb').read()).hexdigest()
    blob_mtime = str(os.path.getmtime(blob_filename))
    uncompiled = 0;
    #
    envs = metadata.get('environ')
    env = envs[0] if envs else None     
    extensions = metadata.get('extension')
    #
    ###################################### navigation arrows
    #
    children = metadata.get('child_uuid')
    parent_metadata, downlink, uplink, leftlink, rightlink = index_arrows(metadata, children)
    #
    if not request.user.is_anonymous:
        a = metadata.access
        access_icon  = get_access_icon(a)
    else: access_icon = ''
    ########################################## permission management
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    if not request.user.has_perm('UUID.view_view', metadata):
        #
        buy_link = buy_label = buy_tooltip = buy_form = None
        ret = can_buy_permission(request.user, metadata, 'view_view')
        if isinstance(ret,(int,float)):
            encoded_contract = encoded_contract_to_buy_permission(request.user, metadata, 'view_view', ret, request=request)
            ## long links do not work in Apache
            # buy_link = django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded_contract })
            buy_form = PurchaseEncodedForm(initial={'encoded':encoded_contract})
            buy_label  = 'Buy for %s' % (ret,)
            buy_tooltip  = 'Buy permission to view this blob for %s' % (ret,)
        else:
            logger.debug('Cannot buy, '+str(ret))
        #
        a = 'Access denied to this content.'
        if request.user.is_anonymous: a += ' Please login.'
        messages.add_message(request, messages.WARNING, a)
        logger.info('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: access denied',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return render(request, 'UUID.html', locals() )
    #
    buy_download_link = buy_download_label = buy_download_tooltip = buy_download_form = None
    download_blob_buttons = []
    if not request.user.has_perm('UUID.download'):
        ret = can_buy_permission(request.user, metadata, 'download')
        if isinstance(ret,(int,float)):
            a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + ('?lang=%s&ext=%s'%(blob_lang,blob_ext)) + '#tools'
            encoded_contract = encoded_contract_to_buy_permission(request.user, metadata, 'download', ret, request=request, redirect_fails=a, redirect_ok=a)
            ## long links do not work in Apache
            # buy_download_link = django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded_contract })
            buy_download_form = PurchaseEncodedForm(initial={'encoded':encoded_contract})
            buy_download_label  = 'Buy for %s :' % (ret,)
            buy_download_tooltip  = 'Buy permission to download this blob for %s' % (ret,)
        else:
            logger.warning('Cannot buy download, '+str(ret))
    else:
        a = Blangs
        if 'mul' in a:
            a += CDlangs
        download_blob_buttons = [ (j, iso3lang2word(j)) for j in a ]
    # TODO
    show_comment = request.user.is_superuser
    #
    #####################################################################
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    #
    #
    its_something_we_would_latex = (env not in ColDoc.latex.environments_we_wont_latex)
    if its_something_we_would_latex:
        ll = view_lang if view_lang in CDlangs else CDlangs[0]
        pdfUUIDurl = django.urls.reverse('ColDoc:pdfframe', kwargs={'NICK':NICK,}) +\
            '?lang=%s&uuid=%s#titlebeforepdf'%(ll, UUID)
        section, anchor = ColDoc.latex.get_specific_html_for_UUID(global_blobs_dir,UUID)
        htmlUUIDurl = django.urls.reverse('ColDoc:html', kwargs={'NICK':NICK,}) +\
             section + '?lang=%s%s'%(ll, anchor)
    else: pdfUUIDurl = htmlUUIDurl = ''
    #
    view_md5 = ''
    view_mtime = ''
    VIEW = ''
    #
    if blob_ext in ColDoc.config.ColDoc_show_as_text:
        blobcontenttype = 'text'
        file = open(blob_filename).read()
        escapedfile = escape(file).replace('\n', '<br>') #.replace('\\', '&#92;')
        if env in ColDoc.latex.environments_we_wont_latex:
            html = '[NO HTML preview for %r]'%(env,)
            pdfurl = ''
            if view_lang:
                all_views = [( view_lang, iso3lang2word_H(view_lang), html, '')]
            else:
                all_views = [( '', '', html, '')]
        elif env == 'main_file' and uuid == coldoc.root_uuid:
            pdfurl = ''
            html = ''
            try:
                b = DMetadata.objects.filter(coldoc=NICK, environ='E_document')[0]
                a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':b.uuid})
                html += (r'<a href="%s">'  % (a,)) + _('Main document') + r'</a>' 
            except:
                logger.exception('cannot find E_document')
            html+='<ul>'
            for b in DMetadata.objects.filter(coldoc=NICK, extension='.tex\n'):
                try:
                    e_ = b.environ
                    if e_ in ColDoc.latex.environments_we_wont_latex or \
                       e_ in ('section','input','include'):
                        a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':b.uuid})
                        s = b.environ or 'blob'
                        s += ' '
                        if e_ == 'section':
                            j = b.get('section')
                        else:
                            j = b.get('section')
                            if not j:
                                j = b.get('original_filename')
                        s += ' , '.join(j)
                        html += r'<li><a href="%s">%s</a></li>' % (a, s)
                except:
                    logger.exception('cannot add blob %r to list',b)
            html+='</ul>'
            all_views = [( blob_lang, iso3lang2word_H(blob_lang), html, '')]
        else:
          all_views = []
          llll = [view_lang]
          if lang == "mul" or view_lang is None:
            llll =  CDlangs
          # show all languages to authors and editors, but not for non-linguistic content
          # TODO maybe add : 'biblio' not in env and
          if lang is None and (request.user.is_editor or request.user.is_author) and \
                                 all((j not in Blangs) for j in ('xzz','und')  ):
            llll =  CDlangs
          for ll in  llll:
            pdfurl = django.urls.reverse('UUID:pdf', kwargs={'NICK':NICK,'UUID':UUID}) +\
                '?lang=%s&ext=%s'%(ll,blob_ext)
            view_md5 =''
            view_mtime = 0
            html = _('[NO HTML AVAILABLE]')
            try:
                a = 'view'
                if ll:
                    a += '_' + ll
                a += '_html'
                a = osjoin(a , 'index.html')
                f = osjoin(blob__dir, a )
                #
                view_md5 = hashlib.md5(open(f,'rb').read()).hexdigest()
                view_mtime = str(os.path.getmtime(f))
                VIEW = a
                #
                html = open(f).read()
                u = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':'000'})
                #
                html = _html_replace(html, u[:-4], uuid, ll, True, children, highlight)
            except FileNotFoundError:
                messages.add_message(request, messages.WARNING, _("HTML preview not available"))
            except:
                logger.exception('Problem when preparing HTML for %r',UUID)
                messages.add_message(request, messages.ERROR ,_("HTML preview not available, internal error"))
            #
            all_views.append(( ll, iso3lang2word_H(ll), html, pdfurl))
    else:
        blobcontenttype = 'image' if (blob_ext in ColDoc.config.ColDoc_show_as_image)  else 'other'
        file = html = escapedfile = ''
        # TODO
        #  a = ... see in `show()`
        # VIEW = 
        #view_md5 = hashlib.md5(open(a,'rb').read()).hexdigest()
        #view_mtime = str(os.path.getmtime(a))
    #
    if lang not in (None,''):
        lang_ = '_' + lang
    else:
        lang_ = ''
    availablelogs = []
    if  request.user.has_perm('UUID.view_log'):
        pref_ = 'main' if UUID == metadata.coldoc.root_uuid else 'view'
        accs_ = ('public','private') if UUID == metadata.coldoc.root_uuid else (None,)
        for l in (Blangs if ('mul' not in Blangs) else CDlangs):
          for ac_ in accs_:
            availablelogs2 = []
            lt_ = iso3lang2word(l)
            if ac_ :
                lt_ += ' ' + _(ac_)
            for e_ in ColDoc.config.ColDoc_allowed_logs:
                a = osjoin(blob__dir, pref_ + '_' + l + e_)
                if os.path.exists(a):
                    a = django.urls.reverse( 'UUID:log',   kwargs={'NICK':NICK,'UUID':UUID})
                    if a[-1] != '/': a += '/'
                    a += '?lang=%s&ext=%s'  % (l,e_)
                    if ac_ :
                        a += '&access=%s' % ac_
                    availablelogs2.append(  (e_ , a ) )
            availablelogs.append( ( lt_ , availablelogs2 ) )
            del availablelogs2
    #
    blobdiff = ''
    # just to be safe
    can_change_blob = request.user.has_perm('UUID.change_blob')
    if not request.user.has_perm('UUID.view_view', metadata):
        html = _('[access denied]')
    if not request.user.has_perm('UUID.view_blob'):
        file = _('[access denied]')
    elif  blobcontenttype == 'text' :
        choices = teh.list_allowed_choices(metadata.environ)
        can_add_blob = request.user.has_perm('ColDocApp.add_blob') and choices and env != 'main_file'
        blobeditform = None
        if  can_add_blob or can_change_blob:
            msgs = []
            latex_filters = []
            for name, label, help, val, fun in transform.get_latex_filters():
                if fun == transform.squash_helper_token2unicode:
                    val = settings.TRANSLATOR is not None
                if fun in ( transform.filter_greek_to_unicode, transform.filter_math_to_unicode):
                    val = coldoc.latex_engine != 'pdflatex'
                latex_filters.append((name, label, help, val, fun))
            blobform_filters = [a[0] for a in latex_filters] 
            blobeditform , uncompiled = _build_blobeditform_data(metadata, request.user, blob_filename,
                                                    blob_ext, blob_lang, choices, can_add_blob, can_change_blob, msgs,
                                                    latex_filters)
            revert_button_class =  'btn-warning'  if uncompiled else 'btn-outline-info'
            compile_button_class=  'btn-warning'  if uncompiled else 'btn-outline-info'
            for l, m in msgs:
                messages.add_message(request, l, m)
            H = difflib.HtmlDiff()
            H._table_template = diff_table_template
            blobdiff = H.make_table(open(blob_filename).read().split('\n'),
                                    blobeditform.initial['blobcontent'].split('\n'),
                                    _('Saved on disk'),_('Your content'), True)
            # html5 does not like those
            #blobdiff = blobdiff.replace('cellspacing="0"','').replace('cellpadding="0"','').replace('rules="groups"','')
    #
    showurl = django.urls.reverse('UUID:show', kwargs={'NICK':NICK,'UUID':UUID}) +\
        '?lang=%s&ext=%s'%(blob_lang,blob_ext)
    #
    a = metadata.latex_return_codes if UUID != metadata.coldoc.root_uuid else metadata.coldoc.latex_return_codes
    latex_error_logs = convert_latex_return_codes(a, NICK, UUID)
    latex_error_logs = latex_error_fix_line_numbers(blobs_dir, anon_dir, uuid, latex_error_logs, load_uuid)
    #
    can_change_metadata = request.user.has_perm('UUID.change_dmetadata')
    if can_change_metadata:
        metadataform = MetadataForm(instance=metadata, initial={'uuid_':uuid,'ext_':blob_ext,'lang_':blob_lang, })
        metadataform.htmlid = "id_form_metadataform"
        ## restrict to allowed choices
        if parent_metadata is not None:
            choices = teh.list_allowed_choices(parent_metadata.environ, extensions)
        elif uuid == coldoc.root_uuid:
            choices = [('main_file','main_file')]
        else: # disconnected node
            choices = [(a,a) for a in ColDoc.config.ColDoc_environments]
            choices += teh.E_choices
        # useless
        metadataform.fields['environ'].choices = choices
        # useful
        metadataform.fields['environ'].widget.choices = choices
        if '.tex' not in extensions or env in ColDoc.config.ColDoc_environments_locked:
            metadataform.fields['environ'].widget.attrs['readonly'] = True
            metadataform.fields['optarg'].widget.attrs['readonly'] = True
    #
    initial_base = {'NICK':NICK, 'UUID':UUID, 'lang':blob_lang,
                    'ext': blob_ext if blob_ext else ''}
    #
    blobuploadform = None
    if blobcontenttype != 'text' and can_change_blob:
        a, m = __allowed_image_mimetypes(blob_ext)
        blobuploadform = BlobUploadForm(initial=initial_base)
        if m:
            blobuploadform.fields['file'].widget.attrs['accept'] = ','.join(m)
        # FIXME this is ineffective
        v = FileExtensionValidator(allowed_extensions=a)
        blobuploadform.fields['file'].validators.append(v)
    #
    other_view_languages = []
    uuid_languages = []
    for val in  (Blangs if ('mul' not in Blangs) else CDlangs) :
        link="/UUID/{nick}/{UUID}/?lang={val}".format(UUID=metadata.uuid,nick=coldoc.nickname,val=val)
        uuid_languages.append((iso3lang2word(val), link))
        if val not in ('mul','und') and val != view_lang:
            other_view_languages.append((iso3lang2word(val), link))
    #
    langforms = []
    # TODO only '.tex' is supported now
    if can_change_metadata and can_change_blob and blob_ext == '.tex':
        bc = 'btn-primary'
        # add
        m = [l for l in CDlangs if l not in Blangs ]
        if m and 'mul' not in Blangs:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'add', initial=initial_base)
            a = bc if (settings.TRANSLATOR is None or 'preamble' in env) else   'border-info'
            langforms.append( (L, 'add', _('Add a language version'), a) )
            #
            if settings.TRANSLATOR is not None:
                L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'translate', initial=initial_base)
                s = _('Translate to language' )
                if 'preamble' in env:
                    s += ' ' + _('(may damage preamble parts)')
                a = 'border-info' if ('preamble' in env) else bc
                langforms.append( (L, 'translate', s, a) )
        # delete
        m = [l for l in Blangs]
        if len(m) > 1 and 'mul' not in Blangs:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'delete', initial=initial_base)
            langforms.append( (L,'delete', _('Delete a language version'), bc) )
        # relabel
        m = [l for l in CDlangs if (l != lang and l not in Blangs) ]
        if m and 'mul' not in Blangs:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'relabel', initial=initial_base)
            langforms.append( (L,'relabel',
                               _('Change the language of this blob from %s to:') % (iso3lang2word(blob_lang),) , bc) )
        # convert to `mul`
        if 'mul' not in Blangs and len(CDlangs) > 1 :
            L = LangForm(choice_list = wrong_choice_list,
                         prefix = 'multlang', initial=initial_base)
            langforms.append( (L,'multlang',_('Change this UUID to <tt>mul</tt> (<i>Multilingual method</i>)'), bc) )
        if 'mul' in Blangs:
            L = LangForm(choice_list =  wrong_choice_list,
                         prefix = 'manual', initial=initial_base)
            langforms.append( (L,'manual',_('Change this UUID to manual language management (non <tt>mul</tt>)'), bc) )
    #
    blob_language = iso3lang2word(blob_lang)
    if view_lang :
        view_language = iso3lang2word(view_lang)
    else:
        view_language = blob_language
    logger.info('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: file served',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
    #
    def reverse_uuid(u):
        l = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':u}) 
        return '<a href="%s">%s</a>' %(l,u)
    def reverse_uuid_link(u):
        return django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':u}) 
    #
    replaces = metadata.get('M_replaces')
    # flatten by punctuation
    replaces = [ a for u in replaces for a in re.split(',|;|/|\n|\t| ',u)]
    replaces = [ a.rstrip('} \n').lstrip('\n {') for a in replaces ]
    replaces = [ a for a in replaces if (a and ColDoc.utils.uuid_valid_symbols.match(a) )]
    replaces = ',\n'.join([reverse_uuid(u)  for u in  replaces ])
    #
    replacedby = ',\n'.join([reverse_uuid(blob.uuid)  for blob in  uuid_replaced_by(coldoc, UUID) ])
    #
    bibliofiles = DMetadata.objects.filter(environ__contains='bibliography').filter(coldoc=coldoc).all()
    bibliolink = ''
    if not bibliofiles:
        bibliofiles = []
    elif request.user.is_editor or request.user.is_author:
        bibliofiles = [ ( (  (b.original_filename.strip() or b.uuid.strip()) + b.extension.strip())  ,\
                          reverse_uuid_link(b.uuid) ) for b in bibliofiles]
    else:
        bibliolink = reverse_uuid_link(bibliofiles[0].uuid) if bibliofiles else ''
        bibliofiles = []
    #
    compilation_in_progress = int( ('compilation_in_progress_' + metadata.uuid) in request.session)
    ajax_views_url = django.urls.reverse('UUID:ajax_views', kwargs={'NICK':NICK,'UUID':UUID})
    #
    MAIN_CONTAINER_CLASS = 'container-fluid' if \
        request.COOKIES.get('main_width') == 'large' else 'container'
    #
    return render(request, 'UUID.html', locals() )



download_template=r"""%% !TeX spellcheck = %(lang)s
%% !TeX encoding = UTF-8
%% !TeX TS-program = %(latex_engine)s
\documentclass %(documentclassoptions)s {%(documentclass)s}
\newif\ifplastex\plastexfalse
%(coldoc_api)s
%(language_conditionals)s
\usepackage{hyperref}
%(latex_macros)s
\def\uuidbaseurl{%(url_UUID)s}
%(preamble)s
\begin{document}
%(begin)s
%(content)s
%(end)s
\end{document}
%%%%%% Local Variables: 
%%%%%% coding: utf-8
%%%%%% mode: latex
%%%%%% TeX-engine: %(latex_engine_emacs)s
%%%%%% End: 
"""

tex_mimetype = 'text/x-tex'

def download(request, NICK, UUID):
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
    #
    q = request.GET
    ext = None
    if 'ext' in q:
        ext = q['ext']
        if not slugp_re.match(ext):
            raise SuspiciousOperation("Invalid ext %r in query." % (ext,))
    lang = q.get('lang')
    if lang is not None and not lang_re.match(lang):
            raise SuspiciousOperation("Invalid lang %r in query." % (lang,))
    #
    download_as = q.get('as',None)
    if download_as is None or download_as not in ('zip','single','email','blob'):
        messages.add_message(request, messages.WARNING, 'Invalid method' )
        logger.warning('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : invalid method',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    for j in q:
        if j not in ('ext','lang','as'):
            messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
    #
    logger.debug('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : entering',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as)
    #
    try:
        filename, uuid, metadata, lang, ext = \
            ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                     ext = ext, lang = lang, 
                                     metadata_class=DMetadata, coldoc=NICK)
    except FileNotFoundError:
        logger.warning('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : cannot find',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as)
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID,lang,ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.exception('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : exception',
                         request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as) 
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    #
    uuid_dir = ColDoc.utils.uuid_to_dir(uuid, blobs_dir=blobs_dir)
    #
    if lang is None or lang == '':
        _lang=''
    else:
        _lang = '_' + lang
    #
    envs = metadata.get('environ')
    env = envs[0] if envs else None
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    #
    _content_type = tex_mimetype
    _content_encoding = 'utf-8'
    # error message
    a = None
    #
    options = _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc)
    # effective file served
    e_f = None
    if not request.user.has_perm('UUID.download'):
        # FIXME this code path is currently unused, and it fails in Apache since URLs are too long
        a = _('Download denied for this content.')
        e_f = None
        ret = can_buy_permission(request.user, metadata, 'download')
        if isinstance(ret,(int,float)):
            encoded_contract = encoded_contract_to_buy_permission(request.user, metadata, 'download', ret, request=request)
            a = django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded_contract })
            return redirect(a)
        else:
            logger.debug('Cannot buy, '+str(ret))
    elif request.user.has_perm('UUID.view_blob') and (download_as == 'blob'):
        e_f = filename
        _content_type , _content_encoding = mimetypes.guess_type(filename)
    elif not request.user.has_perm('UUID.view_view'):
        a = _('Access denied to this content.')
        e_f = None
    elif ext == '.tex' :
        # users with perm('UUID.download') and perm('UUID.view_view')
        # but not perm('UUID.view_blob') : have access to the `squashed view`
        e_f = osjoin( uuid_dir, 'squash'+_lang+'.tex')
        if lang == 'mul':
            # this is otherwise never created
            b = os.path.join(uuid_dir,'blob'+_lang+'.tex')
            s = os.path.join(uuid_dir,'squash'+_lang+'.tex')
            ColDoc.transform.squash_latex(open(osjoin(blobs_dir,b)), open(osjoin(blobs_dir,s),'w'), options,
                                          helper = ColDoc.transform.squash_input_uuid(blobs_dir, metadata, options, load_uuid))
    else:
        # for images, there is currently no difference between
        #`viewing blob` or `viewing view`, so has_perm('UUID.view_view')
        # is sufficient to view the image
        e_f = filename
        _content_type , _content_encoding = mimetypes.guess_type(filename)
        if not is_image_blob(metadata, _content_type):
            a = 'Access denied to this content.'
            e_f = None
    #
    if e_f is None:
        if request.user.is_anonymous: a += ' ' + _('Please login.')
        messages.add_message(request, messages.WARNING, a)
        logger.warning('download ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : '+a,
                    request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    if not os.path.isfile(os.path.join(blobs_dir, e_f)):
        logger.warning('download ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : no file %r',
                    request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as, e_f)
        messages.add_message(request, messages.WARNING, 'Cannot download (you have insufficient priviledges)')
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    #
    logger.info('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : serving %r',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as, e_f)
    #
    if download_as == 'blob':
        content = open(os.path.join(blobs_dir, e_f), 'rb').read()
        response = HttpResponse(content, content_type = _content_type )
        response['Content-Disposition'] = "attachment; filename=" + ( 'ColDoc_%s_UUID_%s_%s%s' % (NICK,UUID,lang,ext))
        return response
    #
    content = open(os.path.join(blobs_dir, e_f), 'r').read()
    #
    its_something_we_would_latex = (env not in ColDoc.latex.environments_we_wont_latex)
    if not its_something_we_would_latex or ( _content_type != tex_mimetype ) :
        logger.info('ip=%r user=%r coldoc=%r uuid=%r ext=%r lang=%r as=%r : not something we would LaTeX',
                    request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, ext, lang, download_as)
        messages.add_message(request, messages.WARNING, 'This blob is not not something we would LaTeX')
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    engine = options.get('latex_engine','pdflatex')
    options['latex_engine_emacs'] = {'xelatex':'xetex','lualatex':'luatex','pdflatex':'default'}[engine]
    #
    options.setdefault('latex_macros',metadata.coldoc.latex_macros_uuid)
    options.setdefault('lang',lang)
    options['language_conditionals'] = '\n'.join(ColDoc.latex.lang_conditionals(lang, langs = coldoc.get_languages()))
    options['coldoc_api'] = ColDoc.config.ColDoc_api_version_macro
    #
    options['begin']=''
    options['end']=''
    environ = metadata.environ
    if environ[:2] == 'E_' and environ not in ( 'E_document', ):
        env = environ[2:]
        options['begin'] = r'\begin{'+env+'}'
        options['end'] = r'\end{'+env+'}'
        if 'split_list' in options and env in options['split_list']:
            options['begin'] += r'\item'
    #
    preambles = []
    preamble = ''
    #
    s = osjoin(os.path.dirname(settings.BASE_DIR), 'tex/ColDocUUID.sty')
    try:
        s = open(s).read()
        preambles.append( ('ColDocUUID.sty', '\\usepackage{ColDocUUID}', s) )
        preamble += '%%%%%%%%%%%%%%%% ColDocUUID.sty\n' + r'\makeatletter' + s + r'\makeatother'
    except:
        preamble += '%%%%%%%%%%%%%%%% internal error ColDocUUID.sty missing\n'
        logger.exception('While adding %r', s)
    for a in ("preamble_definitions", "preamble_" + engine, ):
        m = None
        try:
            m = DMetadata.objects.filter(original_filename__contains = a, coldoc = coldoc).get()
        except:
            logger.warning("No blob has filename %r", a)
            continue
        if m is None:
            continue
        z = None
        try:
            z = ColDoc.utils.choose_blob(blobs_dir = blobs_dir, ext=None, lang = lang, metadata=m)
            f = z[0]
            ext = z[-1]
        except FileNotFoundError as e:
            logger.debug('No choice for filename=%r lang=%r error=%r, retrying w/o lang',a,lang,e)
        if z is None:
            try:
                z = ColDoc.utils.choose_blob(blobs_dir = blobs_dir, lang=None, ext=None, metadata=m)
                f = z[0]
                ext = z[-1]
            except FileNotFoundError as e:
                logger.error('Could not find content for filename=%r metadata=%r error=%r',a,m,e)
        if z is None:
            continue
        else:
            # check permissions
            request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, m)
            if not request.user.has_perm('UUID.download'):
                a = 'Download denied for the subpart %r .' % (a,)
                if request.user.is_anonymous: a += ' Please login.'
                messages.add_message(request, messages.WARNING, a)
            else:
                s=open(osjoin(blobs_dir,f)).read()
                k = {'.sty':'usepackage','.tex':'input'}.get(ext,'input')
                preambles.append( ( (a+ext) , ('\\%s{%s}'%(k,a,)) , s) )
                preamble += '\n%%%%%%%%%%%%%% '+a + '\n'
                if ext == '.sty':
                    preamble += '\\makeatletter\n'
                preamble += s
                if ext == '.sty':
                    preamble += '\\makeatother\n'
    #
    options['documentclassoptions'] = ColDoc.utils.parenthesizes(options.get('documentclassoptions'), '[]')
    #
    if download_as == 'single':
        options['preamble'] = preamble
        options['content'] = '%%%%%% start of ' + UUID + '\n' + content + '\n%%%%%% end of ' + UUID + '\n'
        f = download_template % options
        response = HttpResponse(f, content_type=tex_mimetype)
        response['Content-Disposition'] = "attachment; filename=" + ( 'ColDoc_%s_UUID_%s_%s_document.tex' % (NICK,UUID,lang))
        return response
    #
    options['preamble'] = '\n'.join([j[1] for j in preambles])
    uuidname = '%s_%s_%s.tex' % (NICK,UUID,lang)
    dirname = '%s_%s_%s/' % (NICK,UUID,lang)
    options['content'] = '\input{%s}' % (uuidname,)
    if download_as == 'zip':
        import zipfile, io
        F = io.BytesIO()
        Z = zipfile.ZipFile(F,'w')
        Z.writestr(zinfo_or_arcname=dirname+'main.tex' , data=(download_template % options) , )
        Z.writestr(zinfo_or_arcname=dirname+uuidname , data=content, )
        for a,i,c in preambles:
            Z.writestr(zinfo_or_arcname=dirname+a, data=c, )
        Z.close()
        F.seek(0)
        response = HttpResponse(F, content_type='application/zip')
        response['Content-Disposition'] = "attachment; filename=" + ( 'ColDoc_%s_%s_%s.zip' % (NICK,UUID,lang))
        return response
    #
    if download_as == 'email':
        email_to=request.user.email
        #
        from django.core.mail import EmailMessage
        E = EmailMessage(subject='latex for ColDoc %s UUID %s'%(NICK,UUID),
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[email_to],)
        E.body = 'Find attached the needed documents'
        E.attach(filename='main.tex', content=(download_template % options) , mimetype=tex_mimetype)
        E.attach(filename=uuidname , content=content, mimetype=tex_mimetype)
        for a,i,c in preambles:
            E.attach(filename=a, content=c, mimetype=tex_mimetype)
        try:
            E.send()
        except:
            messages.add_message(request, messages.WARNING, 'Failed to send email')
            return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
        else:
            messages.add_message(request, messages.INFO, 'Email sent to %s'%(email_to,))
            return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    # should not reach this point
    assert False
