import os, sys, mimetypes, http
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

import django
from django.shortcuts import render, redirect
from django.http import HttpResponse, QueryDict
from django.db.models import Q
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib import messages

import ColDoc.utils, ColDocDjango

from ColDoc.utils import slug_re

from django.conf import settings

from ColDocDjango.UUID import views as UUIDviews

from django.shortcuts import get_object_or_404, render

from .models import DColDoc

from ColDocDjango.UUID.models import DMetadata, ExtraMetadata

def index(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    #coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,NICK)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    c=c[0]
    return render(request, 'coldoc.html', {'coldoc':c,'NICK':c.nickname})

def html(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    c=c[0]
    return UUIDviews.view_(request, NICK, c.root_uuid, '_html', None, subpath, prefix='main')

def pdf(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    c=c[0]
    return UUIDviews.view_(request, NICK, c.root_uuid, '.pdf', None, subpath, prefix='main')

def search(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    if request.method == 'POST' :
        searchtoken = request.POST.get('searchtoken')
        if searchtoken is None:
            logger.error('Search POST with not "searchtoken" : hacking attemp?')
            return HttpResponse("Bad ... bad ..."%(request.method,),
                                status=http.HTTPStatus.BAD_REQUEST)
    else:
        assert request.method == 'GET'
        searchtoken = request.GET.get('searchtoken')
        if searchtoken is None:
            # this happens when the user logs in or logs out while on the search page
            return redirect(django.urls.reverse('ColDoc:index',
                                                kwargs={'NICK':NICK,})) 
        #return HttpResponse("Method %r not allowed"%(request.method,),status=http.HTTPStatus.BAD_REQUEST)
    #
    if len(searchtoken) <= 1:
        messages.add_message(request, messages.WARNING, "Search key is too short.")
        return index(request, NICK)
    #
    coldoc = list(DColDoc.objects.filter(nickname = NICK))
    if not coldoc:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    coldoc=coldoc[0]
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    # UUID
    if len(searchtoken) <= 8 and len(searchtoken) >= 3 :
        maybe_uuid = True
        try:
            uuid_ = ColDoc.utils.uuid_check_normalize(searchtoken)
        except ValueError:
            uuid_list = []
            maybe_uuid = False
        else:
            uuid_list = DMetadata.objects.filter(coldoc=coldoc, uuid=uuid_)
    else:
        maybe_uuid = False
        uuid_list = []
    #
    if request.user.is_authenticated and coldoc.anonymous_can_view :
        # FIXME , would like to use `has_perm('UUID.view_view')`
        # but this currently works only on a per-blob basis:
        # so we should filter this list accordingly
        index_list = ExtraMetadata.objects.filter(Q(key__contains='M_index') & 
                                                  Q(blob__coldoc=coldoc) &
                                                  Q(value__contains=searchtoken))
    else:
        index_list = []
    if request.user.has_perm('UUID.view_blob'):
        label_list = ExtraMetadata.objects.filter(Q(key__endswith='M_label') & 
                                                  Q(blob__coldoc=coldoc) &
                                                  Q(value__contains=searchtoken))
        ref_list = ExtraMetadata.objects.filter((Q(key__endswith='M_ref') |
                                                 Q(key__endswith='M_eqref') |
                                                 Q(key__endswith='M_pageref') )   & 
                                                Q(blob__coldoc=coldoc) &
                                                Q(value__contains=searchtoken))
    else:
        label_list = ref_list = []
    # TODO search in text
    # shortcut
    if len(uuid_list)==1 and not label_list and not index_list and not ref_list:
        return redirect(django.urls.reverse('UUID:index',
                                            kwargs={'NICK':NICK,'UUID':uuid_list[0].uuid}))
    
    return render(request, 'search.html',
                  {'coldoc':coldoc, 'NICK':coldoc.nickname, 'maybe_uuid':maybe_uuid,
                   'uuid_list':uuid_list,'label_list':label_list,'ref_list':ref_list,
                   'index_list':index_list,
                   })
