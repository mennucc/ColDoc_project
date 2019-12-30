import django
from django.shortcuts import render
from django.http import HttpResponse, QueryDict

import ColDoc.utils, ColDocDjango

from ColDocDjango import settings

from django.shortcuts import get_object_or_404, render

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
         'lang':lang, 'ext':ext, 'file':file, 'blobcontenttype':content }
    return render(request, 'UUID.html', c)


