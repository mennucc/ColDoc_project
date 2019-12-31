import os,sys

import django
from django.shortcuts import render
from django.http import HttpResponse, QueryDict

import ColDoc.utils, ColDocDjango

from ColDocDjango import settings

from django.shortcuts import get_object_or_404, render


def pdf(request, UUID):
    blobs_dir = settings.COLDOC_SITE_CONFIG['coldoc']['blobs_dir']
    msg = ''
    try:
        a = ColDoc.utils.uuid_check_normalize(UUID)
        if a != UUID:
            msg += "UUID was normalized from %r to %r"%(UUID,a)
        UUID = a
    except ValueError as e:
        return HttpResponse("Invalid UUID %r. \n Reason: %r" % (UUID,e))
    #
    q = request.GET
    ext = '.tex'
    if 'ext' in q:
        ext = q['ext']
    langs = []
    if 'lang' in q:
        langs = [q['lang']]
    download='download' in q
    #for j in q:
    #    if j not in ('ext','lang'):
    #        msg += 'Ignored query %r'%(j,)
    #
    try:
        uuid, uuid_dir, metadata = ColDoc.utils.resolve_uuid(uuid=UUID, uuid_dir=None,
                                                       blobs_dir = blobs_dir)
        if metadata['environ'][0] == 'preamble':
            return  HttpResponse('There is no PDF for the preamble',content_type='text/plain')
        if metadata['environ'][0] == 'E_document':
            return  HttpResponse('No need of PDF for this `document` blob, refer the main blob',
                                 content_type='text/plain')
        # TODO should serve using external server see
        #   https://stackoverflow.com/questions/2687957/django-serving-media-behind-custom-url
        #   
        n = None
        langs += metadata['lang'] + [None]
        for l in langs:
            if l is not None:
                l='_'+l
            else:
                l=''
            n = os.path.join(blobs_dir, uuid_dir,"fakelatex"+l+".pdf")
            if os.path.isfile(n):
                break
            else:
                n = None
        if n is None:
            return HttpResponse("Cannot find PDF for UUID %r , looking for languages in %r." % (UUID,langs),
                                content_type='text/plain')
        fsock = open(n,'rb')
        response = HttpResponse(fsock, content_type='application/pdf')
        if download:
            response['Content-Disposition'] = "attachment; filename=ColDoc-%s.pdf" % (UUID,)
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
            msg += "UUID was normalized from %r to %r"%(UUID,a)
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
            msg += 'Ignored query %r'%(j,)
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
         'lang':lang, 'ext':ext, 'file':file, 'blobcontenttype':content }
    return render(request, 'UUID.html', c)


