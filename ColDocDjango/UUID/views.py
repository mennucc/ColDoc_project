import os, sys, mimetypes, http, copy, json, hashlib, difflib, shutil, subprocess, re
from os.path import join as osjoin

try:
    import pycountry
except:
    pycountry = None

import logging
logger = logging.getLogger(__name__)


import django
from django.shortcuts import get_object_or_404, render, redirect
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
from ColDoc.utils import slug_re, slugp_re, is_image_blob, html2text, iso3lang2word, uuid_to_dir, gen_lang_metadata
from ColDocDjango.utils import get_email_for_user
from ColDoc.blob_inator import _rewrite_section, _parse_obj
from ColDoc import TokenizerPassThru

from .models import DMetadata, DColDoc

from .shop import encoded_contract_to_buy_permission, can_buy_permission

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
        self.fields['langchoice'] = forms.ChoiceField(choices=choice_list,
                                                      label="Language",
                                                      #help_text="Language choice"
                                                      )

    class Meta:
        fields = ('langchoice', )


# show prologue in web UI, to ease debugging
__debug_view_prologue__ = False


class BlobUploadForm(forms.Form):
    htmlid = "id_form_blobuploadform"
    file = forms.FileField(help_text="File to upload  — will replace the blob's content")
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput(),required = False)
    mimetype = forms.CharField(widget=forms.HiddenInput(),required = False)    
    
class BlobEditForm(forms.Form):
    class Media:
        js = ('UUID/js/blobeditform.js',)
    htmlid = "id_form_blobeditform"
    ## remembers first line of sections, or \uuid when present
    prologue = forms.CharField(widget = forms.TextInput(attrs={'class': 'form-text w-75'}) \
                               if __debug_view_prologue__ else \
                               forms.HiddenInput(),
                               required = False, label='Prologue',
                               help_text='First line of text file, automatically generated')
    # the real blobcontent
    blobcontent = forms.CharField(widget=forms.HiddenInput(),required = False)
    # what the user can edit
    BlobEditTextarea=forms.CharField(label='Blob content',required = False,
                                     widget=forms.Textarea(attrs={'class': 'form-text w-100'}),
                                     help_text='Edit the blob content')
    BlobEditComment=forms.CharField(label='Comment',required = False,
                                    widget=forms.TextInput(attrs={'class': 'form-text w-75'}),
                                    help_text='Comment for this commit')
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput(),required = False)
    file_md5 = forms.CharField(widget=forms.HiddenInput())
    selection_start = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    selection_end = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    split_selection = forms.BooleanField(label='Insert a child',required = False,
                                         widget = forms.CheckboxInput(attrs = {'onclick' : "hide_and_show();", }),
                                         help_text="Insert a child at cursor (if a piece of text is selected, it will be moved into the child)")
    split_environment = forms.ChoiceField(label="environment",
                                          help_text="environment for newly created blob")
    split_add_beginend = forms.BooleanField(label='Add begin/end',required = False,help_text="add a begin{}..end{} around the splitted ")

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
        warnings.append('Internal error when parsing optarg %r for  blob %r ' % (optarg,uuid))
        optarg = []
    if env in ColDoc.config.ColDoc_environments_sectioning:
        if blobcontent.startswith('\\'+env):
            try:
                j = blobcontent.index('\n')
                prologue = blobcontent[:j]
                if optarg:
                    shortprologue = '\\' + env + ''.join(optarg) 
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
                warnings.append('Added initial \\%s line' % env)
            else:
                warnings.append('Missing initial \\%s line' % env)
    elif env not in ColDoc.config.ColDoc_do_not_write_uuid_in:
        if not blobcontent.startswith('\\uuid'):
            logger.error('Blob %r does not start with \\uuid',uuid)
            warnings.append('Missing initial, hidden, \\uuid line in blob %r' % (uuid,))
            prologue = '\\uuid{%s}%%' % (uuid,)
        else:
            try:
                j = blobcontent.index('\n')
                prologue = blobcontent[:j]
                blobeditdata = blobcontent[j+1:]
            except:
                logger.exception('Could not remove uuid line from blob %r', uuid)
                prologue = '%'
    return shortprologue, prologue, blobeditdata, warnings

def _build_blobeditform_data(NICK, UUID,
                             env,  optarg,
                             user, filename,
                             ext, lang,
                             choices,
                             can_add_blob, can_change_blob,
                             msgs):
    file_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    blobcontent = open(filename).read()
    # the first line contains the \uuid command or the \section{}\uuid{}
    shortprologue, prologue, blobeditdata, warnings = __extract_prologue(blobcontent, UUID, env, optarg)
    if '\\uuid{' in blobeditdata:
        warnings.append('(Why is there a  \\uuid  in this blob ?)')    
    for wp in warnings:
        msgs.append(( messages.WARNING, wp))
    #
    user_id = str(user.id)
    a = filename[:-4] + '_' + user_id + '_editstate.json'
    #
    D = {'BlobEditTextarea':  blobeditdata,
         'prologue' : json.dumps( (shortprologue, prologue) ),
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
                          'Editstate ignored: ' + m ))
            N ={}
    if N:
        if N['file_md5'] != file_md5:
            msgs.append(( messages.WARNING,
                         'File was changed on disk: check the diff' ))
            N['file_md5'] = file_md5
        elif N['blobcontent'] != blobcontent:
            msgs.append(( messages.INFO,
                          'Your saved changes are yet uncompiled' ))
        D.update(N)
    blobeditform = BlobEditForm(initial=D)
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
    return blobeditform


def md5(request, NICK, UUID, FILE):
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID, accept_anon=True)
    assert  isinstance(FILE,str) and '..' not in FILE
    assert ( FILE.startswith('blob') or FILE.startswith('view'))
    metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    if not request.user.has_perm('UUID.view_view') and FILE.startswith('view'):
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation("Permission denied")
    if not request.user.has_perm('UUID.view_blob') and FILE.startswith('blob'):
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation("Permission denied")
    from ColDoc.utils import uuid_to_dir
    filename = osjoin(blobs_dir, uuid_to_dir(UUID), FILE)
    if not os.path.isfile(filename):
        return HttpResponse(filename, status=http.HTTPStatus.NOT_FOUND)
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
    newprologue = ''
    output = ''
    sources = None
    warn_notfirst_ = False
    warn_dup_ = False
    seen_one_sec_ = False
    # give it some context
    thetex = TeX()
    #thetex.ownerDocument.context.loadPackage(thetex, 'article.cls', {})
    thetex.input(copy.copy(blobeditarea),  Tokenizer=TokenizerPassThru.TokenizerPassThru)
    thetex.currentInput[0].pass_comments = True
    itertokens = thetex.itertokens()
    while itertokens is not None:
        try:
            tok = next(itertokens)
        except StopIteration:
            itertokens = None
            break
        if isinstance(tok, TokenizerPassThru.Comment):
            output += '%' + str(tok)
        elif isinstance(tok, plasTeX.Tokenizer.EscapeSequence):
            if not str(tok.macroName) == env:
                if str(tok).startswith('active::'):
                    output += tok.source
                else:
                    output += '\\' + str(tok)
            elif not seen_one_sec_ :
                obj = Base.section()
                thetex.currentInput[0].pass_comments = False
                src, sources, attributes = _parse_obj(obj, thetex)
                thetex.currentInput[0].pass_comments = True
                if any([ ('\n' in s) for s in sources]):
                    weird_prologue.append('Keep the\\%s{...} command all in one line.' % (env,))
                    sources = list(map( lambda x : x.replace('\n',' '), sources ))
                ignoreme, newprologue = _rewrite_section(sources, uuid, env)
                seen_one_sec_ = True
            else:
                warn_dup_ = True
                if str(tok).startswith('active::'):
                    output += tok.source
                else:
                    output += '\\' + str(tok)
        else:
            output += tok.source
            if not seen_one_sec_ :
                warn_notfirst_ = True
    if not seen_one_sec_ :
        weird_prologue.append('Please add a \\%s{...} command in first line.' % (env,))
    elif warn_notfirst_:
        weird_prologue.append('The command \\%s{...} was moved to first line.' % (env,))
        newprologue += '%\n'
    if warn_dup_ :
        weird_prologue.append('The blob should contain only one occurrence of \\%s{...}.' % (env,))
    return newprologue, output, sources

def   _put_back_prologue(prologue, blobeditarea, env, uuid):
    sources = None
    weird_prologue = []
    newprologue = ''
    if env in ColDoc.config.ColDoc_environments_sectioning :
        # try to parse \\section
        try:
            #
            newprologue, blobeditarea, sources = _parse_for_section(blobeditarea, env, uuid, weird_prologue)
        except:
            logger.exception('While parsing \\section')
            weird_prologue.append('Internal error while parsing for \\%s{...}.' % (env,))
        blobcontent = newprologue + blobeditarea
    elif env not in ColDoc.config.ColDoc_do_not_write_uuid_in:
        newprologue = '\\uuid{%s}%%\n' % (uuid,)
        blobcontent = newprologue + blobeditarea
    else:        
        blobcontent = blobeditarea
    return blobcontent, newprologue, sources , weird_prologue

def postlang(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    #
    actions = ['add','relabel','delete']
    prefix = request.POST.get('button')
    if prefix not in actions:
        raise SuspiciousOperation("Wrong action: %r"%prefix)
    #
    l = coldoc.get_languages() + ['mul','zxx','und']
    ll = [(a,a) for a in l]
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
    assert len(lang_) == 3 and slug_re.match(lang_)
    assert slugp_re.match(ext_)
    #
    metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    can_change_blob = request.user.has_perm('UUID.change_blob')
    can_change_metadata = request.user.has_perm('UUID.change_dmetadata')
    #can_add_blob = request.user.has_perm('ColDocApp.add_blob')
    if not (can_change_metadata and can_change_blob):
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    D = uuid_to_dir(UUID, blobs_dir)
    D = osjoin(blobs_dir, D)
    dst = osjoin(D,'blob_'+langchoice_+ext_)
    src = osjoin(D,'blob_'+lang_+ext_)
    #
    redirectlang_ = langchoice_
    #
    if not os.path.exists(src):
        messages.add_message(request,messages.WARNING,
                             'A blob with language %r extension %r does not exist'%
                             (iso3lang2word(lang_),ext_))
        logger.warning('A blob with language %r extension %r does not exist' % (lang_,ext_))
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    if prefix == 'add' or prefix == 'relabel':
        L = metadata.get_languages()
        #
        if langchoice_ not in L and prefix == 'add':
            metadata.lang = '\n'.join(L + [langchoice_]) + '\n'
            metadata.save()
        #
        if os.path.exists(dst):
            messages.add_message(request,messages.WARNING,
                                 'A blob with language %r extension %r already exists'%
                                 (iso3lang2word(langchoice_),ext_))
        else:
            if prefix == 'relabel':
                L[L.index(lang_)] = langchoice_
                metadata.lang = '\n'.join(L) + '\n'
                metadata.save()
            #
            if prefix == 'add' or langchoice_ == 'mul':
                logger.warning('copy %r to %r',src,dst)
                string = open(src).read()
                string = ColDoc.utils.replace_language_in_inputs(string, lang_, langchoice_)
                open(dst,'w').write(string)
                messages.add_message(request,messages.INFO,
                                     'A blob with language %r extension %r was created copying from %r.\nPlease translate it.'%
                                     (iso3lang2word(langchoice_),ext_,iso3lang2word(lang_)))
            else:
                logger.warning('rename %r to %r',src,dst)
                string = open(src).read()
                string = ColDoc.utils.replace_language_in_inputs(string, lang_, langchoice_)
                open(dst,'w').write(string)
                os.unlink(src)
                if langchoice_ != 'mul':
                    for j in os.listdir(D):
                        if j[:4] in ('blob','view') and j[5:8] == lang_:
                            h = j[:5] + langchoice_ + j[8:]
                            dst = osjoin(D,h)
                            src = osjoin(D,j)
                            logger.warning('rename %r to %r',src,dst)
                            os.rename(src, dst)
    elif prefix == 'delete':
        redirectlang_ = lang_
        L = metadata.get_languages()
        if langchoice_ in L:
            del L[L.index(langchoice_)]
            metadata.lang = '\n'.join(L)  + '\n'
            metadata.save()
        else:
            logger.warning(' lang %r not in %r',langchoice_,L)
    else:
        messages.add_message(request,messages.ERROR, 'unimplemented %r %r'%(prefix,langchoice_))
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + \
                    '?lang=%s&ext=%s'%(redirectlang_,ext_) )




def postupload(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    #
    form=BlobUploadForm(data=request.POST, files=request.FILES)
    #
    if not form.is_valid():
        a = "Invalid form: "+repr(form.errors)
        return HttpResponse(a,status=http.HTTPStatus.BAD_REQUEST)
    uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                         blobs_dir = blobs_dir, coldoc = NICK,
                                                         metadata_class=DMetadata)
    #    
    env = metadata.environ
    file_ = form.cleaned_data['file']
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    type__ = form.cleaned_data['mimetype']
    assert UUID == uuid_ and NICK == nick_
    assert len(lang_) == 3 and slug_re.match(lang_)
    assert slugp_re.match(ext_)
    #
    l = ('_'+lang_) if lang_ else ''
    dest = os.path.join(blobs_dir, uuid_dir, 'blob' + l + ext_)
    #
    try:
        with open(dest + '~~', 'wb+') as destination:
            for chunk in file_.chunks():
                destination.write(chunk)
        os.rename(dest + '~~', dest)
    except:
        logger.exception('failed %r',dest)
        messages.add_message(request,messages.ERROR, 'File upload failed')
    ## nope this uses the extension
    #_type_ , _encod_ = mimetypes.guess_type(dest)
    if file_.content_type != type__:
        messages.add_message(request,messages.ERROR,   'File uploaded is %r instead of %r' % ( file_.content_type , type__) )
    #
    metadata.blob_modification_time_update()
    metadata.save()
    #
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')


def  __relatex(request, coldoc, metadata, coldoc_dir, blobs_dir, lang, messages, all_messages):
    gen_lang_metadata(metadata, blobs_dir, coldoc.get_languages())
    languages = [lang]  if 'mul' not in metadata.get_languages() else coldoc.get_languages()
    for thelang in languages:
        rh, rp = _latex_blob(request, coldoc_dir, blobs_dir, coldoc, thelang, metadata)
        if rh and rp:
            a = 'Compilation of LaTeX succeded (%r)' % thelang
            messages.add_message(request,messages.INFO,a)
        else:
            a = 'Compilation of LaTeX failed (%r)' % thelang
            messages.add_message(request,messages.WARNING,a)
        all_messages.append(a)


def postedit(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    #
    assert 1 == ( 'compile' in request.POST ) + ( 'save' in request.POST ) + ( 'save_no_reload' in request.POST )
    #
    form=BlobEditForm(request.POST)
    #
    metadata = DMetadata.load_by_uuid(uuid=UUID, coldoc=coldoc)
    env = metadata.environ
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    ## https://docs.djangoproject.com/en/dev/topics/forms/
    a = teh.list_allowed_choices(env)
    form.fields['split_environment'].choices = a
    if not a:
        form.fields['split_environment'].required = False
    #
    if not form.is_valid():
        a = "Invalid form: "+repr(form.errors)
        if 'save_no_reload'  in request.POST:
            return JsonResponse({"message":a})
        return HttpResponse(a,status=http.HTTPStatus.BAD_REQUEST)
    prologue = form.cleaned_data['prologue']
    # convert to UNIX line ending 
    blobcontent  = re.sub("\r\n", '\n',  form.cleaned_data['blobcontent'] )
    blobeditarea = re.sub("\r\n", '\n',  form.cleaned_data['BlobEditTextarea'] )
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    file_md5 = form.cleaned_data['file_md5']
    split_selection_ = form.cleaned_data['split_selection']
    split_environment_ = form.cleaned_data['split_environment']
    selection_start_ = int(form.cleaned_data['selection_start'])
    selection_end_ = int(form.cleaned_data['selection_end'])
    split_add_beginend_ = form.cleaned_data['split_add_beginend']
    assert UUID == uuid_ and NICK == nick_
    assert len(lang_) == 3 and slug_re.match(lang_)
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
    env = metadata.environ
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
    if file_md5 != real_file_md5 and 'compile' in request.POST:
        a = "The file was changed on disk: compile aborted"
        messages.add_message(request,messages.ERROR, a)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')
    # put back prologue in place
    blobcontent, newprologue, sources , weird_prologue = _put_back_prologue(prologue, blobeditarea, env, UUID)
    form.cleaned_data['blobcontent'] = blobcontent
    # some checks
    try:
        a = json.loads(prologue)
        shortprologue, prologue = a
    except:
        shortprologue = None
        logger.exception('cannot json decode %r', prologue)
        weird_prologue.append('Internal JSON error')
    if split_selection_:
        if shortprologue is None:
            weird_prologue.append('Cannot split material when there are internal errors')
            split_selection_ = False
        elif weird_prologue:
            weird_prologue.append('Cannot split material when there are header errors')
            split_selection_ = False
        elif shortprologue and not blobeditarea.startswith(shortprologue + '\n'):
            weird_prologue.append('Sorry, cannot split material when the first line was changed')
            split_selection_ = False
        else:
            displacement = len(prologue) - len(shortprologue)
            selection_start_  = max(selection_start_ + displacement, 0)
            selection_end_    = max(selection_end_ + displacement, selection_end_)
    #
    for wp in weird_prologue:
        logger.warning(' in %r %s', UUID, wp)
    # save state of edit form
    if can_change_blob:
        user_id = str(request.user.id)
        file_editstate = filename[:-4] + '_' + user_id + '_editstate.json'
        json.dump(form.cleaned_data, open(file_editstate,'w'))
    #
    a = '' if ( file_md5 == real_file_md5 ) else "The file was changed on disk: check the diff"
    if 'save_no_reload' in request.POST:
        H = difflib.HtmlDiff()
        blobdiff = H.make_table(open(filename).readlines(),
                                blobcontent.split('\n'),
                                'Orig','New', True)
        for wp in weird_prologue:
            a += '\n' + wp
        return JsonResponse({"message":a, 'blobdiff':blobdiff, 'blob_md5': real_file_md5})
    for wp in  weird_prologue:
        messages.add_message(request,messages.WARNING, wp)
    if 'save'  in request.POST:
        messages.add_message(request,messages.INFO,'Saved')
        if a:
            messages.add_message(request,messages.WARNING, a)
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')
    # diff
    file_lines_before = open(filename).readlines()
    shutil.copy(filename, filename+'~~')
    #
    uuid_as_html = '<a href="%s">%s</a>' %(
        request.build_absolute_uri(django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':uuid})), uuid)
    # write new content
    if can_change_blob:
        open(filename,'w').write(blobcontent)
        metadata.blob_modification_time_update()
        if sources is not None:
            metadata.optarg = json.dumps(sources)
        metadata.save()
    else:
        pass # may want to check that form was not changed...
    # TODO we should have two copies, for html and for text form of each message
    all_messages = []
    #
    from ColDoc.latex import environments_we_wont_latex
    from ColDoc.utils import reparse_blob
    #
    if split_selection_:
        from helper import add_blob
        addsuccess, addmessage, addnew_uuid = \
            add_blob(logger, request.user, settings.COLDOC_SITE_ROOT, nick_, uuid_, 
                 split_environment_, lang_, c_lang, selection_start_ , selection_end_, split_add_beginend_)
        if addsuccess:
            new_uuid_as_html = '<a href="%s">%s</a>' %(
                request.build_absolute_uri(django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':addnew_uuid})),
                addnew_uuid)
            addmessage = ("Created blob with UUID %s, please edit %s to properly input it (a stub \\input was inserted for your convenience)"%
                          (new_uuid_as_html, uuid_as_html))
            messages.add_message(request,messages.INFO,addmessage)
            addmetadata = DMetadata.load_by_uuid(uuid=addnew_uuid,coldoc=coldoc)
            add_extension = addmetadata.get('extension')
        else:
            add_extension = []
            messages.add_message(request,messages.WARNING,addmessage)
        all_messages.append(addmessage)
        if  '.tex' in add_extension:
            addfilename, adduuid, addmetadata, addlang, addext = \
                ColDoc.utils.choose_blob(uuid=addnew_uuid, blobs_dir = blobs_dir,
                                         ext = ext_, lang = lang_,
                                         metadata_class=DMetadata, coldoc=NICK)
            # parse it for metadata
            def warn(msg):
                all_messages.append('Metadata change in new blob: '+msg)
                messages.add_message(request,messages.INFO,'In new blob: '+msg)
            reparse_blob(addfilename, addmetadata, blobs_dir, warn)
            # compile it
            if split_environment_ not in environments_we_wont_latex:
                rh, rp = _latex_blob(request, coldoc_dir, blobs_dir, coldoc, lang, addmetadata)
                if rh and rp:
                    a = 'Compilation of new blob succeded'
                    messages.add_message(request,messages.INFO,a)
                else:
                    a = 'Compilation of new blob failed'
                    messages.add_message(request,messages.WARNING,a)
                all_messages.append(a)
    #
    # parse it to refresh metadata (after splitting)
    def warn(msg):
        all_messages.append('Metadata change in blob: '+msg)
        messages.add_message(request,messages.INFO,msg)
    reparse_blob(filename, metadata, blobs_dir, warn)
    #
    if ext_ == '.tex'  and metadata.environ not in environments_we_wont_latex:
        __relatex(request, coldoc, metadata, coldoc_dir, blobs_dir, lang, messages, all_messages)
    logger.info('ip=%r user=%r coldoc=%r uuid=%r ',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
    email_to = _interested_emails(coldoc,metadata)
    #
    if not email_to:
        logger.warning('No author has a validated email %r', metadata)
    else:
        a = "User '%s' changed %s - %s" % (request.user , metadata.coldoc.nickname, metadata.uuid)
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
                               'Orig','New', True)
        try:
            j  = blobdiff.index('<body>') + 6
            blobdiff = blobdiff[:j] + '<ul><li>' + '\n<li>'.join(all_messages) + \
                '</ul>\n<h1>File differences for ' + uuid_as_html + '</h1>\n' + blobdiff[j:]
        except:
            logger.exception('While preparing ')
        else:
            E.attach_alternative(blobdiff, 'text/html')
        # text version
        try:
            all_messages = map(html2text, all_messages)
        except:
            logger.exception('While preparing ')
        P = subprocess.run(['diff', '-u', filename + '~~', filename, ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False, universal_newlines=True )
        message = '*) ' +  '\n*) '.join(all_messages) + '\n\n*** File differences ***\n\n' +  P.stdout
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
        D['blobcontent'] = open(filename).read()
        D['split_selection'] = False
        D['selection_start'] = str(selection_start_)
        D['selection_end'] = str(selection_start_)
        D['lang'] = lang
        D['UUID'] = uuid
        D['ext'] = ext
        json.dump(D, open(file_editstate,'w'))
    #
    return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + '?lang=%s&ext=%s'%(lang_,ext_) + '#blob')

def postmetadataedit(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    #
    uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                   blobs_dir = blobs_dir, coldoc = NICK,
                                                   metadata_class=DMetadata)
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
    assert len(lang_) == 3 and slug_re.match(lang_)
    assert slugp_re.match(ext_)
    environ_ = form.cleaned_data['environ']
    if uuid != uuid_ :
        logger.error('Hacking attempt %r',request.META)
        raise SuspiciousOperation('UUID Mismatch')
    if ext_ not in metadata.get('extension') :
        messages.add_message(request,messages.WARNING,'Internal problem, check the metadata again %r != %r' %([ext_], metadata.extension))
    #
    form.save()
    messages.add_message(request,messages.INFO,'Changes saved')
    #
    from ColDoc.latex import environments_we_wont_latex
    if ext_ =='.tex'  and metadata.environ not in environments_we_wont_latex:
        __relatex(request, coldoc, metadata, coldoc_dir, blobs_dir, lang_, messages, [])
    logger.info('ip=%r user=%r coldoc=%r uuid=%r ',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID)
    #
    email_to = _interested_emails(coldoc,metadata)
    if not email_to:
        logger.warning('No author has a validated email %r', metadata)
    else:
        a = "User '%s' changed metadata in %s - %s" % (request.user , metadata.coldoc.nickname, metadata.uuid)
        r = get_email_for_user(request.user)
        P = subprocess.run(['diff', '-u', baF+'~~', baF, ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False, universal_newlines=True )
        message = P.stdout
        after = open(metadata.backup_filename()).readlines()
        H = difflib.HtmlDiff()
        html_message = H.make_file(before, after, 'Orig','New', True)
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

def _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc):
    from ColDoc.latex import prepare_options_for_latex
    options = prepare_options_for_latex(coldoc_dir, blobs_dir, DMetadata, coldoc)
    #
    url = django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':'000'})[:-4]
    url = request.build_absolute_uri(url)
    # used for PDF
    options['url_UUID'] = url
    #
    from ColDocDjango.transform import squash_helper_ref
    def foobar(*v, **k):
        " helper factory"
        return squash_helper_ref(coldoc, *v, **k)
    options["squash_helper"] = foobar
    options['metadata_class'] = DMetadata
    # used by the deduping mechanism
    options['coldoc_site_root']  = settings.COLDOC_SITE_ROOT
    options['dedup_root'] = settings.DEDUP_ROOT
    options['dedup_url'] = settings.DEDUP_URL
    return options

def _latex_blob(request, coldoc_dir, blobs_dir, coldoc, lang, metadata):
    options = _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc)
    from ColDoc import latex   
    return latex.latex_blob(blobs_dir, metadata, lang, options=options)

def _latex_uuid(request, coldoc_dir, blobs_dir, coldoc, uuid, metadata):
    options = _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc)
    from ColDoc import latex   
    return latex.latex_uuid(blobs_dir, uuid, metadata=metadata, options=options)


###############################################################

@xframe_options_sameorigin
def pdf(request, NICK, UUID):
    return view_(request, NICK, UUID, '.pdf', 'application/pdf')

@xframe_options_sameorigin
def html(request, NICK, UUID, subpath=None):
    return view_(request, NICK, UUID, '_html', None, subpath)

@xframe_options_sameorigin
def show(request, NICK, UUID):
    return view_(request, NICK, UUID, None, None, None, prefix='blob')

def log(request, NICK, UUID):
    return view_(request, NICK, UUID, None, None, None, prefix='log')


def view_(request, NICK, UUID, _view_ext, _content_type, subpath = None, prefix='view'):
    #
    logger.debug('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r : entering',
                request.META.get('REMOTE_ADDR'), request.user.username,
                NICK,UUID,_view_ext,_content_type,subpath,prefix)
    # do not allow subpaths for non html
    assert _view_ext == '_html' or subpath is None
    assert _view_ext in ('_html','.pdf',None)
    assert prefix in ('main','view','blob','log')
    assert ( isinstance(NICK,str) and slug_re.match(NICK) )  or isinstance(NICK,DColDoc)
    assert ( isinstance(UUID,str) and slug_re.match(UUID) )
    #
    if isinstance(NICK,DColDoc):
        coldoc = NICK
        NICK = coldoc.nickname
    else:
        coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            # TODO this is not shown
            messages.add_message(request, messages.WARNING,
                                 "UUID was normalized from %r to %r"%(UUID,a))
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
    # used for main document logs
    access = q.get('access')
    assert access is None or slugp_re.match(access)
    #
    if prefix == 'log' and  _view_ext not in ColDoc.config.ColDoc_allowed_logs:
        return HttpResponse("Permission denied (log)", status=http.HTTPStatus.UNAUTHORIZED)
    #
    # if user is editor, provide true access
    blobs_subdir = 'blobs'
    blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
    if prefix == 'main':
        request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
        if not request.user.has_perm('UUID.view_view') :
            # users.user_has_perm() will grant `public` access to editors
            blobs_subdir = 'anon'
            blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
    if not os.path.isdir(blobs_dir):
        return HttpResponse("No such ColDoc %r.\n" % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    #
    lang = q.get('lang')
    if lang is not None and ( len(lang) != 3 or not slug_re.match(lang)):
            raise SuspiciousOperation("Invalid lang %r in query." % (lang,))
    download='download' in q
    #for j in q:
    #    if j not in ('ext','lang'):
    #        messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
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
        langs = [lang] if (lang is not None) else ( Blangs + [None] )
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
            assert l in (None,'') or slug_re.match(l)
            if l not in (None,''):
                l='_'+l
            else:
                l=''
            n = os.path.join(blobs_dir, uuid_dir, pref_ + l + _view_ext)
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
        if _content_type is None:
            if _view_ext in ColDoc.config.ColDoc_allowed_logs :
                _content_type = 'text/plain'
                _content_encoding = 'utf-8'
            else:
                _content_type , _content_encoding = mimetypes.guess_type(n)
        #
        if prefix=='blob' and not ( request.user.has_perm('UUID.view_blob') or is_image_blob(metadata, _content_type) ):
            logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r pref_=%r : permission denied',
                        request.META.get('REMOTE_ADDR'), request.user.username,
                        NICK,UUID,_view_ext,_content_type,subpath,pref_)
            return HttpResponse("Permission denied (blob)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        #
        if _content_type == 'text/html':
            f = open(n).read()
            a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':'001'})
            f = f.replace(ColDoc.config.ColDoc_url_placeholder,a[:-4])
            response = HttpResponse(f, content_type=_content_type)
        else:
            fsock = open(n,'rb')
            response = HttpResponse(fsock, content_type=_content_type)
        if download:
            response['Content-Disposition'] = "attachment; filename=ColDoc-%s%s" % (UUID,_view_ext)
        logger.info('ip=%r user=%r coldoc=%r uuid=%r _view_ext=%r _content_type=%r subpath=%r prefix=%r lang=%r pref_=%r blobs_subdir=%r : content served',
                    request.META.get('REMOTE_ADDR'), request.user.username,
                    NICK,UUID,_view_ext,_content_type,subpath,prefix,lang,pref_,blobs_subdir)
        return response
    
    except FileNotFoundError:
        logger.warning('FileNotFoundError user=%r coldoc=%r uuid=%r ext=%r lang=%r',request.user.username,NICK,UUID,_view_ext,lang)
        return HttpResponse("Cannot find UUID %r with langs=%r , extension=%r." % (UUID,langs,_view_ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.exception(e)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e),
                            status=http.HTTPStatus.INTERNAL_SERVER_ERROR)

def get_access_icon(access):
    ACCESS_ICONS = {'open':    ('<img src="%s" style="height: 12pt"  data-toggle="tooltip" title="%s">' % \
                                (static('ColDoc/Open_Access_logo_PLoS_white.svg'),DMetadata.ACCESS_CHOICES[0][1])), #
                    'public':  ('<span style="font-size: 12pt" data-toggle="tooltip" title="%s">%s</span>' %\
                                (DMetadata.ACCESS_CHOICES[1][1],chr(0x1F513),)), # '🔓'
                    'private': ('<span style="font-size: 12pt" data-toggle="tooltip" title="%s">%s</span>' %\
                               (DMetadata.ACCESS_CHOICES[2][1],chr(0x1F512),)), # '🔒'
                        }
    return ACCESS_ICONS[access]


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
    q = request.GET
    ext = None
    if 'ext' in q:
        ext = q['ext']
        if not slugp_re.match(ext):
            raise SuspiciousOperation("Invalid ext %r in query." % (ext,))
    lang = q.get('lang')
    if lang is not None and ( len(lang) != 3 or not slug_re.match(lang) ):
            raise SuspiciousOperation("Invalid lang %r in query." % (lang,))
    for j in q:
        if j not in ('ext','lang'):
            messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
            logger.warning( 'Ignored query %r'%(j,) )
    #
    try:
        view_filename, uuid, metadata, view_lang, ext = \
            ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                     ext = ext, lang = lang, 
                                     metadata_class=DMetadata, coldoc=NICK)
    except FileNotFoundError:
        logger.warning('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: file not found',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID,lang,ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.error('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: file not found',
                       request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    #
    Blangs = metadata.get_languages()
    CDlangs = coldoc.get_languages()
    #
    if 'mul' in Blangs:
        filename = osjoin( os.path.dirname(view_filename), 'blob_mul.tex')
        blob_lang = 'mul'
    else:
        blob_lang = view_lang
        filename = view_filename
    BLOB = os.path.basename(filename)
    blob_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    blob_mtime = str(os.path.getmtime(filename))
    #
    envs = metadata.get('environ')
    env = envs[0] if envs else None     
    extensions = metadata.get('extension')
    #
    ###################################### navigation arrows
    #
    parent_metadata = parent_uuid = uplink = downlink = None
    try:
        j = metadata.get('child_uuid')
        if j:
            downlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[0]})
        j = metadata.get('parent_uuid')
        if j:
            parent_uuid = j[0]
            parent_metadata = DMetadata.load_by_uuid(parent_uuid, metadata.coldoc)
            uplink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':parent_uuid})
        elif env != 'main_file':
            logger.warning('no parent for UUID %r',UUID)
    except:
        logger.exception('WHY?')
    leftlink = rightlink = None 
    if parent_metadata is not None:
        j = list(parent_metadata.get('child_uuid'))
        try:
            i = j.index(uuid)
            if i>0:
                leftlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i-1]})
            if i<len(j)-1:
                rightlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i+1]})
        except:
            logger.exception('problem finding siblings for UUID %r',UUID)
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
    if not request.user.has_perm('UUID.download'):
        ret = can_buy_permission(request.user, metadata, 'download')
        if isinstance(ret,(int,float)):
            a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) + ('?lang=%s&ext=%s'%(lang,ext)) + '#tools'
            encoded_contract = encoded_contract_to_buy_permission(request.user, metadata, 'download', ret, request=request, redirect_fails=a, redirect_ok=a)
            ## long links do not work in Apache
            # buy_download_link = django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded_contract })
            buy_download_form = PurchaseEncodedForm(initial={'encoded':encoded_contract})
            buy_download_label  = 'Buy for %s :' % (ret,)
            buy_download_tooltip  = 'Buy permission to download this blob for %s' % (ret,)
        else:
            logger.warning('Cannot buy download, '+str(ret))
    # TODO
    show_comment = request.user.is_superuser
    #
    #####################################################################
    #
    from ColDoc.utils import tree_environ_helper
    teh = tree_environ_helper(blobs_dir = blobs_dir)
    #
    pdfurl = django.urls.reverse('UUID:pdf', kwargs={'NICK':NICK,'UUID':UUID}) +\
        '?lang=%s&ext=%s'%(view_lang,ext)
    #
    its_something_we_would_latex = (env not in ColDoc.latex.environments_we_wont_latex)
    if its_something_we_would_latex:
        pdfUUIDurl = django.urls.reverse('ColDoc:pdf', kwargs={'NICK':NICK,}) +\
            '?lang=%s&ext=%s#UUID:%s'%(view_lang, ext, UUID)
        section, anchor = ColDoc.latex.get_specific_html_for_UUID(global_blobs_dir,UUID)
        htmlUUIDurl = django.urls.reverse('ColDoc:html', kwargs={'NICK':NICK,}) +\
             section +\
            '?lang=%s&ext=%s%s'%(view_lang, ext, anchor)
    else: pdfUUIDurl = htmlUUIDurl = ''
    #
    view_md5 = ''
    view_mtime = ''
    VIEW = ''
    #
    if ext in ColDoc.config.ColDoc_show_as_text:
        blobcontenttype = 'text'
        file = open(view_filename).read()
        escapedfile = escape(file).replace('\n', '<br>') #.replace('\\', '&#92;')
        if env in ColDoc.latex.environments_we_wont_latex:
            html = '[NO HTML preview for %r]'%(env,)
            pdfurl = ''
        elif env == 'main_file':
            pdfurl = ''
            html = ''
            try:
                b = DMetadata.objects.filter(coldoc=NICK, environ='E_document')[0]
                a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':b.uuid})
                html += r'<a href="%s">main document</a>' % (a,)
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
        else:
            try:
                d = os.path.dirname(filename) + '/'
                a = 'view'
                if view_lang:
                    a += '_' + view_lang
                a += '_html/index.html'
                VIEW = a
                a = d + a
                view_md5 = hashlib.md5(open(a,'rb').read()).hexdigest()
                view_mtime = str(os.path.getmtime(a))
                html = open(a).read()
                a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':'000'})
                html = html.replace(ColDoc.config.ColDoc_url_placeholder,a[:-4])
                # help plasTeX find its images
                html = html.replace('src="images/','src="html/images/')
            except:
                logger.exception('Problem when preparing HTML for %r',UUID)
                messages.add_message(request, messages.WARNING,"HTML preview not available")
                html = '[NO HTML AVAILABLE]'
    else:
        blobcontenttype = 'image' if (ext in ColDoc.config.ColDoc_show_as_image)  else 'other'
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
        d = os.path.dirname(filename)
        pref_ = 'main' if UUID == metadata.coldoc.root_uuid else 'view'
        for e_ in ColDoc.config.ColDoc_allowed_logs:
            a = osjoin(d, pref_ + lang_ + e_)
            if os.path.exists(a):
                a = django.urls.reverse( 'UUID:log',   kwargs={'NICK':NICK,'UUID':UUID})
                if a[-1] != '/': a += '/'
                a += '?lang=%s&ext=%s'  % (lang,e_)
                availablelogs.append(  (e_, a ) )
    #
    blobdiff = ''
    # just to be safe
    can_change_blob = request.user.has_perm('UUID.change_blob')
    if not request.user.has_perm('UUID.view_view', metadata):
        html = '[access denied]'
    if not request.user.has_perm('UUID.view_blob'):
        file = '[access denied]'
    elif  blobcontenttype == 'text' :
        choices = teh.list_allowed_choices(metadata.environ)
        can_add_blob = request.user.has_perm('ColDocApp.add_blob') and choices and env != 'main_file'
        blobeditform = None
        if  can_add_blob or can_change_blob:
            msgs = []
            blobeditform = _build_blobeditform_data(NICK, UUID, env, metadata.optarg, request.user, filename,
                                                    ext, blob_lang, choices, can_add_blob, can_change_blob, msgs)
            for l, m in msgs:
                messages.add_message(request, l, m)
            H = difflib.HtmlDiff()
            blobdiff = H.make_table(open(filename).read().split('\n'),
                                    blobeditform.initial['blobcontent'].split('\n'),
                                    'Orig','New', True)
    #
    showurl = django.urls.reverse('UUID:show', kwargs={'NICK':NICK,'UUID':UUID}) +\
        '?lang=%s&ext=%s'%(view_lang,ext)
    #
    from ColDocDjango.utils import convert_latex_return_codes
    a = metadata.latex_return_codes if UUID != metadata.coldoc.root_uuid else metadata.coldoc.latex_return_codes
    latex_error_logs = convert_latex_return_codes(a, NICK, UUID)
    #
    can_change_metadata = request.user.has_perm('UUID.change_dmetadata')
    if can_change_metadata:
        metadataform = MetadataForm(instance=metadata, initial={'uuid_':uuid,'ext_':ext,'lang_':blob_lang, })
        metadataform.htmlid = "id_form_metadataform"
        ## restrict to allowed choices
        if parent_metadata is not None:
            choices = teh.list_allowed_choices(parent_metadata.environ, extensions)
        else:
            choices = [('main_file','main_file')]
        # useless
        metadataform.fields['environ'].choices = choices
        # useful
        metadataform.fields['environ'].widget.choices = choices
        if '.tex' not in extensions or env in ColDoc.config.ColDoc_environments_locked:
            metadataform.fields['environ'].widget.attrs['readonly'] = True
            metadataform.fields['optarg'].widget.attrs['readonly'] = True
    #
    mimetype = mimetypes.types_map.get(ext,'')
    initial_base = {'NICK':NICK,'UUID':UUID,'ext':ext,'lang':blob_lang,'mimetype':mimetype}
    blobuploadform = BlobUploadForm(initial=initial_base)
    if mimetype:
        blobuploadform.fields['file'].widget.attrs['accept'] = mimetype
    else:
        logger.warning('Extension %r is not in mimetypes.types_map', ext)
    # FIXME this is ineffective
    a = ('.jpg','.jpeg') if ( ext in ('.jpg','.jpeg') ) else (ext,)
    v = FileExtensionValidator(allowed_extensions=a)
    blobuploadform.fields['file'].validators.append(v)
    #    
    other_view_languages = []
    for val in  (Blangs if ('mul' not in Blangs) else CDlangs) :
        if val not in ('mul','und') and val != view_lang:
            link="/UUID/{nick}/{UUID}/?lang={val}".format(UUID=metadata.uuid,nick=coldoc.nickname,val=val)
            other_view_languages.append((iso3lang2word(val), link))
    #
    langforms = []
    # TODO only '.tex' is supported now
    if can_change_metadata and can_change_blob and ext == '.tex':
        # add
        m = [l for l in CDlangs if l not in Blangs ]
        if m:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'add', initial=initial_base)
            langforms.append( (L,'add','add a language version') )
        # delete
        m = [l for l in Blangs]
        if len(m) > 1:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'delete', initial=initial_base)
            langforms.append( (L,'delete','delete a language version') )
        # relabel
        m = [l for l in CDlangs if (l != lang and l not in Blangs) ]
        if len(Blangs) == 1 and 'mul' not in Blangs and 'mul' != lang:
            m = ['mul'] + m
        if m:
            L = LangForm(choice_list = [ (a,iso3lang2word(a)) for a in m ],
                         prefix = 'relabel', initial=initial_base)
            langforms.append( (L,'relabel','change the language of this blob') )
    #
    view_language = iso3lang2word(view_lang)
    blob_language = iso3lang2word(blob_lang)
    logger.info('ip=%r user=%r coldoc=%r uuid=%r lang=%r ext=%r: file served',
                request.META.get('REMOTE_ADDR'), request.user.username, NICK, UUID, lang, ext)
    return render(request, 'UUID.html', locals() )



download_template=r"""%% !TeX spellcheck = %(lang)s
%% !TeX encoding = UTF-8
%% !TeX TS-program = %(latex_engine)s
\documentclass %(documentclassoptions)s {%(documentclass)s}
\newif\ifplastex\plastexfalse
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
    #
    q = request.GET
    ext = None
    if 'ext' in q:
        ext = q['ext']
        if not slugp_re.match(ext):
            raise SuspiciousOperation("Invalid ext %r in query." % (ext,))
    lang = q.get('lang')
    if lang is not None and (len(lang) != 3 or not slug_re.match(lang) ):
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
        a = 'Download denied for this content.'
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
        a = 'Access denied to this content.'
        e_f = None
    elif ext == '.tex' :
        # users with perm('UUID.download') and perm('UUID.view_view')
        # but not perm('UUID.view_blob') : have access to the `squashed view`
        e_f = osjoin( uuid_dir, 'squash'+_lang+'.tex')
        if lang == 'mul':
            # this is otherwise never created
            b = os.path.join(uuid_dir,'blob'+_lang+'.tex')
            s = os.path.join(uuid_dir,'squash'+_lang+'.tex')
            ColDoc.transform.squash_latex(b, s, blobs_dir, options,
                                          helper = ColDoc.transform.squash_input_uuid(blobs_dir, metadata, options))
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
        if request.user.is_anonymous: a += ' Please login.'
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
        preamble += '%%%%%%%%%%%%%%%% ColDocUUID.sty\n' + s
    except:
        preamble += '%%%%%%%%%%%%%%%% internal error ColDocUUID.sty missing\n'
        logger.exception('While adding %r', s)
    for a in ("preamble_definitions", "preamble_" + engine, ):
        m = None
        try:
            m = DMetadata.objects.filter(original_filename = a, coldoc = coldoc).get()
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
        except ColDoc.utils.ColDocException as e:
            logger.debug('No choice for filename=%r lang=%r error=%r, retrying w/o lang',a,lang,e)
        if z is None:
            try:
                z = ColDoc.utils.choose_blob(blobs_dir = blobs_dir, lang=None, ext=None, metadata=m)
                f = z[0]
                ext = z[-1]
            except ColDoc.utils.ColDocException as e:
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
