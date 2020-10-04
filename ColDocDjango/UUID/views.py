import os, sys, mimetypes, http, copy, json
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)


import django
from django.shortcuts import render
from django.http import HttpResponse, QueryDict
from django.contrib import messages
from django import forms
from django.conf import settings
from django.forms import ModelForm
from django.core.exceptions import SuspiciousOperation

from ColDoc.utils import slug_re

from django.views.decorators.clickjacking import xframe_options_sameorigin

import ColDoc.utils, ColDoc.latex, ColDocDjango

from django.shortcuts import get_object_or_404, render, redirect

from .models import DMetadata, DColDoc

##############################################################

class MetadataForm(ModelForm):
    class Meta:
        model = DMetadata
        fields = ['author', 'access', 'environ','optarg','latex_documentclass_choice']

###############################################################

# https://docs.djangoproject.com/en/dev/topics/forms/

def _environ_choices_(blobs_dir):
    choices=[('section','section')]
    f = osjoin(blobs_dir, '.blob_inator-args.json')
    if not os.path.exists(f):
        logger.error("File of blob_inator args does not exit: %r\n"%(f,))
    else:
        with open(f) as a:
            blobinator_args = json.load(a)
        for a in (blobinator_args['split_environment'] + blobinator_args['split_list']):
            if a not in ('document','main_file'):
                choices.append(( 'E_'+a , a))
    return choices


class BlobEditForm(forms.Form):
    class Media:
        js = ('ColDoc/js/blobeditform.js',)
    htmlid = "id_form_blobeditform"
    BlobEditTextarea=forms.CharField(label='Blob content',
                                     widget=forms.Textarea(attrs={'class': 'form-text w-100'}),
                                     help_text='Edit the blob content')
    BlobEditComment=forms.CharField(label='Comment',required = False,
                                    widget=forms.TextInput(attrs={'class': 'form-text w-75'}),
                                    help_text='Comment for this commit')
    UUID = forms.CharField(widget=forms.HiddenInput())
    NICK = forms.CharField(widget=forms.HiddenInput())
    ext  = forms.CharField(widget=forms.HiddenInput())
    lang = forms.CharField(widget=forms.HiddenInput(),required = False)
    selection_start = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    selection_end = forms.CharField(widget=forms.HiddenInput(),initial=-1)
    split_selection = forms.BooleanField(label='Split',required = False,
                                         widget = forms.CheckboxInput(attrs = {'onclick' : "hide_and_show();", }),
                                         help_text="Split selected text so that it becomes a new blob")
    split_environment = forms.ChoiceField(label="environment",
                                          help_text="environment for newly created blob")
    split_add_beginend = forms.BooleanField(label='Add begin/end',required = False,help_text="add a begin{}..end{} around the splitted ")

def common_checks(request, NICK, UUID):
    if not slug_re.match(UUID):
        raise SuspiciousOperation("Invalid UUID %r." % (UUID,))
    if not slug_re.match(NICK):
        raise SuspiciousOperation("Invalid ColDoc %r." % (NICK,))
    if request.user.is_anonymous:
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

def postedit(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
    #
    form=BlobEditForm(request.POST)
    #
    choices = _environ_choices_(blobs_dir)
    form.fields['split_environment'].choices = choices
    #
    if not form.is_valid():
        return HttpResponse("Invalid form: "+repr(form.errors),status=http.HTTPStatus.BAD_REQUEST)
    blobcontent = form.cleaned_data['BlobEditTextarea']
    uuid_ = form.cleaned_data['UUID']
    nick_ = form.cleaned_data['NICK']
    lang_ = form.cleaned_data['lang']
    ext_ = form.cleaned_data['ext']
    split_selection_ = form.cleaned_data['split_selection']
    split_environment_ = form.cleaned_data['split_environment']
    selection_start_ = int(form.cleaned_data['selection_start'])
    selection_end_ = int(form.cleaned_data['selection_end'])
    split_add_beginend_ = form.cleaned_data['split_add_beginend']
    assert UUID == uuid_ and NICK == nick_
    #
    filename, uuid, metadata, lang, ext = \
        ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                 ext = ext_, lang = lang_, 
                                 metadata_class=DMetadata, coldoc=NICK)
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    if not request.user.has_perm('UUID.change_blob'):
        logger.error('Hacking attempt',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    # write new content
    open(filename,'w').write(blobcontent)
    metadata.blob_modification_time_update()
    metadata.save()
    # parse it to refresh metadata
    from ColDoc.utils import reparse_blob
    def warn(msg):
        messages.add_message(request,messages.INFO,msg)
    reparse_blob(filename, metadata, blobs_dir, warn)
    #
    from ColDoc.latex import environments_we_wont_latex
    #
    if split_selection_:
        from ColDocDjango.helper import add_blob
        addsuccess, addmessage, addnew_uuid = \
            add_blob(logger, request.user, settings.COLDOC_SITE_ROOT, nick_, uuid_, 
                 split_environment_, lang_, selection_start_ , selection_end_, split_add_beginend_)
        if addsuccess:
            addfilename, adduuid, addmetadata, addlang, addext = \
                    ColDoc.utils.choose_blob(uuid=addnew_uuid, blobs_dir = blobs_dir,
                                             ext = ext_, lang = lang_, 
                                             metadata_class=DMetadata, coldoc=NICK)
            messages.add_message(request,messages.INFO,addmessage)
            if ext_ == '.tex' and split_environment_ not in environments_we_wont_latex:
                rh, rp = _latex_blob(request, blobs_dir, coldoc, adduuid, lang, addmetadata)
                if rh and rp:
                    messages.add_message(request,messages.INFO,'Compilation of new blob succeded')
                else:
                    messages.add_message(request,messages.WARNING,'Compilation of new blob failed')
        else:
            messages.add_message(request,messages.WARNING,addmessage)
    #
    #
    if ext_ == '.tex'  and metadata.environ not in environments_we_wont_latex:
        rh, rp = _latex_blob(request,blobs_dir,coldoc,uuid,lang,metadata)
        if rh and rp:
            messages.add_message(request,messages.INFO,'Compilation of LaTeX succeded')
        else:
            messages.add_message(request,messages.WARNING,'Compilation of LaTeX failed')
    return index(request, NICK, UUID)

def postmetadataedit(request, NICK, UUID):
    if request.method != 'POST' :
        return redirect(django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}))
    #
    coldoc, coldoc_dir, blobs_dir = common_checks(request, NICK, UUID)
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
    form=MetadataForm(request.POST, instance=metadata)
    #
    if not form.is_valid():
        return HttpResponse("Invalid form: "+repr(form.errors),status=http.HTTPStatus.BAD_REQUEST)
    form.save()
    messages.add_message(request,messages.INFO,'Changes saved')
    return index(request, NICK, UUID)

def _latex_blob(request,blobs_dir,coldoc,uuid,lang,metadata):
    a = osjoin(blobs_dir, '.blob_inator-args.json')
    blob_inator_args = json.load(open(a))
    assert isinstance(blob_inator_args,dict)
    options = copy.copy(blob_inator_args)
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
    options['metadata_class'] = ColDoc.utils.FMetadata
    #
    from ColDoc import latex
    return latex.latex_blob(blobs_dir, metadata, uuid=uuid, lang = lang, options=options)

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

def view_(request, NICK, UUID, _view_ext, _content_type, subpath = None, prefix='view'):
    #
    # do not allow subpaths for non html
    assert _view_ext == '_html' or subpath is None
    assert _view_ext in ('_html','.pdf',None)
    assert prefix in ('main','view','blob')
    #
    if not slug_re.match(UUID):
        return HttpResponse("Invalid UUID %r (for %r)." % (UUID,_content_type), status=http.HTTPStatus.BAD_REQUEST)
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r (for %r)." % (NICK,_content_type), status=http.HTTPStatus.BAD_REQUEST)
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
            assert slug_re.match(q['ext'])
            _view_ext = '.' + q['ext']
        else:
            return HttpResponse("must specify extension", status=http.HTTPStatus.NOT_FOUND)
    #
    # TODO if user is editor, provide true access
    if prefix == 'main' and not request.user.is_superuser :
        blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'anon')
    else:
        blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
    if not os.path.isdir(blobs_dir):
        return HttpResponse("No such ColDoc %r.\n" % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    #
    langs = []
    if 'lang' in q:
        l = q['lang']
        assert l=='' or slug_re.match(l)
        langs = [l]
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
            return HttpResponse("Permission denied (view)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        if prefix=='blob' and not request.user.has_perm('UUID.view_blob'):
            return HttpResponse("Permission denied (blob)",
                                status=http.HTTPStatus.UNAUTHORIZED)
        #
        env = metadata.get('environ')[0]
        if env in ColDoc.latex.environments_we_wont_latex and _view_ext == '_html':
            return  HttpResponse('There is no %r for %r' % (_view_ext, metadata['environ'][0]), content_type='text/plain')
        # TODO should serve using external server see
        #   https://stackoverflow.com/questions/2687957/django-serving-media-behind-custom-url
        #   
        n = None
        isdir = False
        langs += metadata.get('lang') + [None]
        for l in langs:
            assert l in (None,'') or slug_re.match(l)
            if l not in (None,''):
                l='_'+l
            else:
                l=''
            n = os.path.join(blobs_dir, uuid_dir, prefix+l+_view_ext)
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
        if n is None:
            return HttpResponse("Cannot find blob..%s.%s, subpath %r, for UUID %r , looking for languages in %r." %\
                                (prefix,_view_ext,subpath,UUID,langs),
                                content_type='text/plain', status=http.HTTPStatus.NOT_FOUND)
        if _content_type is None:
            _content_type , _content_encoding = mimetypes.guess_type(n)
        logger.debug("Serving: %r %r"%(n,_content_type))
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
        return response
    
    except FileNotFoundError:
        return HttpResponse("Cannot find UUID %r with langs=%r , extension=%r." % (UUID,langs,_view_ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        logger.exception(e)
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e),
                            status=http.HTTPStatus.INTERNAL_SERVER_ERROR)


def index(request, NICK, UUID):
    if not slug_re.match(UUID):
        return HttpResponse("Invalid UUID %r." % (UUID,), status=http.HTTPStatus.BAD_REQUEST)
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
    if not os.path.isdir(blobs_dir):
        return HttpResponse("No such ColDoc %r.\n" % (NICK,), status=http.HTTPStatus.NOT_FOUND)
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
        assert slug_re.match(q['ext'])
        ext = '.'+q['ext']
    lang = None
    if 'lang' in q:
        lang = q['lang']
        assert lang=='' or slug_re.match(lang)
    for j in q:
        if j not in ('ext','lang'):
            messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
    #
    try:
        filename, uuid, metadata, lang, ext = \
            ColDoc.utils.choose_blob(uuid=UUID, blobs_dir = blobs_dir,
                                     ext = ext, lang = lang, 
                                     metadata_class=DMetadata, coldoc=NICK)
    except FileNotFoundError:
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID,lang,ext),
                            status=http.HTTPStatus.NOT_FOUND)
    except Exception as e:
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e), status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    #
    ########################################## permission management
    #
    request.user.associate_coldoc_blob_for_has_perm(metadata.coldoc, metadata)
    if not request.user.has_perm('UUID.view_view'):
        a = 'Access denied to this content.'
        if request.user.is_anonymous: a += ' Please login.'
        messages.add_message(request, messages.WARNING, a)
    #
    # TODO
    show_comment = request.user.is_superuser
    #
    #####################################################################
    #
    pdfurl = django.urls.reverse('UUID:pdf', kwargs={'NICK':NICK,'UUID':UUID}) +\
        '?lang=%s&ext=%s'%(lang,ext[1:])
    #
    if ext in ColDoc.config.ColDoc_show_as_text:
        blobcontenttype = 'text'
        file = open(filename).read()
        env = metadata.get('environ')[0]
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
            for b in DMetadata.objects.filter(coldoc=NICK):
                try:
                    env = b.environ
                    if env in ColDoc.latex.environments_we_wont_latex or \
                       env in ('section','input','include'):
                        a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':b.uuid})
                        s = b.environ or 'blob'
                        s += ' '
                        if env == 'section':
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
                a = os.path.dirname(filename)+'/view'
                if lang:
                    a += '_' + lang
                    a += '_html/index.html'
                html = open(a).read()
                a = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':'000'})
                html = html.replace(ColDoc.config.ColDoc_url_placeholder,a[:-4])
                # help plasTeX find its images
                html = html.replace('src="images/','src="html/images/')
            except:
                messages.add_message(request, messages.WARNING,"HTML preview not available")
                html = '[NO HTML AVAILABLE]'
    else:
        blobcontenttype = 'other'
        file = html = ''
    # just to be safe
    if not request.user.has_perm('UUID.view_view'):
        html = '[access denied]'
    if not request.user.has_perm('UUID.view_blob'):
        file = '[access denied]'
    elif  blobcontenttype == 'text' :
        if request.user.has_perm('UUID.change_blob'):
            choices = _environ_choices_(blobs_dir)
            blobeditform = BlobEditForm(initial={'BlobEditTextarea':  file,
                                                 'NICK':NICK,'UUID':uuid,'ext':ext,'lang':lang,
                                                 })
            blobeditform.fields['split_environment'].choices = choices
    #
    try:
        j = metadata.get('child_uuid')[0]
        downlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j})
    except:
        downlink = None
    try:
        j = metadata.get('parent_uuid')[0]
        uplink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j})
    except:
        logger.debug('no parent for UUID %r',UUID)
        uplink = j = None
    leftlink = rightlink = None 
    if j is not None:
        p = DMetadata.load_by_uuid(j,NICK)
        j = p.get('child_uuid')
        try:
            j = sorted(j)
            i = j.index(uuid)
            if i>0:
                leftlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i-1]})
            if i<len(j)-1:
                rightlink = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':j[i+1]})
        except:
            logger.exception('problem finding siblings for UUID %r',UUID)
    #
    showurl = django.urls.reverse('UUID:show', kwargs={'NICK':NICK,'UUID':UUID}) +\
        '?lang=%s&ext=%s'%(lang,ext[1:])
    #
    metadataform = MetadataForm(instance=metadata)
    if '.tex' not in metadata.get('extension'):
        metadataform.fields['environ'].widget.attrs['readonly'] = True
        metadataform.fields['optarg'].widget.attrs['readonly'] = True
    return render(request, 'UUID.html', locals() )


