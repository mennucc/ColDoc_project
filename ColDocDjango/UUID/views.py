import os, sys, mimetypes

import logging
logger = logging.getLogger(__name__)


import django
from django.shortcuts import render
from django.http import HttpResponse, QueryDict
from django.contrib import messages

from django.views.decorators.clickjacking import xframe_options_sameorigin

import ColDoc.utils, ColDocDjango

from ColDocDjango import settings

from django.shortcuts import get_object_or_404, render

@xframe_options_sameorigin
def pdf(request, UUID):
    return view_(request, UUID, '.pdf', 'application/pdf')

@xframe_options_sameorigin
def html(request, UUID, subpath=None):
    return view_(request, UUID, '_html', None, subpath)

def view_(request, UUID, _view_ext, _content_type, subpath = None):
    blobs_dir = settings.COLDOC_SITE_CONFIG['coldoc']['blobs_dir']
    msg = ''
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            # TODO this is not shown
            messages.add_message(request, messages.WARNING,
                                 "UUID was normalized from %r to %r"%(UUID,a))
        UUID = a
    except ValueError as e:
        return HttpResponse("Invalid UUID %r. \n Reason: %r" % (UUID,e))
    #
    q = request.GET
    # currently ignored
    ext = '.tex'
    if 'ext' in q:
        ext = q['ext']
    #
    langs = []
    if 'lang' in q:
        langs = [q['lang']]
    download='download' in q
    #for j in q:
    #    if j not in ('ext','lang'):
    #        messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
    #
    try:
        uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                       blobs_dir = blobs_dir)
        if metadata['environ'][0] == 'preamble':
            return  HttpResponse('There is no %r for the preamble' % (_view_ext,), content_type='text/plain')
        if metadata['environ'][0] == 'E_document':
            return  HttpResponse('No need of %r for this `document` blob, refer the main blob' % (_view_ext,),
                                 content_type='text/plain')
        # TODO should serve using external server see
        #   https://stackoverflow.com/questions/2687957/django-serving-media-behind-custom-url
        #   
        n = None
        isdir = False
        langs += metadata['lang'] + [None]
        for l in langs:
            if l is not None:
                l='_'+l
            else:
                l=''
            n = os.path.join(blobs_dir, uuid_dir,"view"+l+_view_ext)
            if subpath is not None:
                n = os.path.join(n,subpath)
            logger.warning(n)
            if os.path.isfile(n):
                break
            elif os.path.isdir(n) and os.path.isfile(n+'/index.html'):
                n+='/index.html'
                isdir=True
                break
            else:
                n = None
        if n is None:
            return HttpResponse("Cannot find %r, subpath %r, for UUID %r , looking for languages in %r." %\
                                (_view_ext,subpath,UUID,langs),
                                content_type='text/plain')
        if _content_type is None:
            _content_type , _content_encoding = mimetypes.guess_type(n)
        logger.warning("Serving: %r %r"%(n,_content_type))
        fsock = open(n,'rb')
        response = HttpResponse(fsock, content_type=_content_type)
        if download:
            response['Content-Disposition'] = "attachment; filename=ColDoc-%s%s" % (UUID,_view_ext)
        return response
    
    except FileNotFoundError:
        return HttpResponse("Cannot find UUID %r with langs=%r , extension=%r." % (UUID,langs,ext))
    except Exception as e:
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e))


def index(request, UUID):
    blobs_dir = settings.COLDOC_SITE_CONFIG['coldoc']['blobs_dir']
    msg = ''
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            # https://docs.djangoproject.com/en/3.0/ref/contrib/messages/
            messages.add_message(request, messages.WARNING,
                                 "UUID was normalized from %r to %r"%(UUID,a))
        UUID = a
    except ValueError as e:
        return HttpResponse("Invalid UUID %r. \n Reason: %r" % (UUID,e))
    #
    q = request.GET
    ext = '.tex'
    if 'ext' in q:
        ext = q['ext']
    lang = None
    if 'lang' in q:
        lang = q['lang']
    for j in q:
        if j not in ('ext','lang'):
            messages.add_message(request, messages.WARNING, 'Ignored query %r'%(j,) )
    #
    try:
        uuid, uuid_dir, m = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                       blobs_dir = blobs_dir)
        filename, uuid, metadata, lang, ext = ColDoc.utils.choose_blob(uuid=uuid, \
                                                                    uuid_dir=uuid_dir, blobs_dir = blobs_dir,
                                                                    ext = ext, lang = lang)
    except FileNotFoundError:
        return HttpResponse("Cannot find UUID %r with lang=%r , extension=%r." % (UUID,lang,ext))
    except Exception as e:
        return HttpResponse("Some error with UUID %r. \n Reason: %r" % (UUID,e))
    #
    if ext == '.tex':
        content = 'text'
        file = open(filename).read()
    else:
        content = 'other'
        file = ''
    c = {'UUID':UUID, 'metadata':metadata, 'message':msg,
         'pdfurl':('/UUID/%s/pdf'%(UUID,)),
         'htmlurl':('/UUID/%s/html'%(UUID,)),
         'lang':lang, 'ext':ext, 'file':file, 'blobcontenttype':content }
    return render(request, 'UUID.html', c)


