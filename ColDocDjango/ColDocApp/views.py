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
from django.forms import ModelForm

import ColDoc.utils, ColDocDjango

from ColDoc.utils import slug_re

from django.conf import settings

from ColDocDjango.UUID import views as UUIDviews

from django.shortcuts import get_object_or_404, render

from .models import DColDoc

from ColDocDjango.UUID.models import DMetadata, ExtraMetadata

class ColDocForm(ModelForm):
    class Meta:
        model = DColDoc
        exclude = []
        exclude = ['headline']
        fields = '__all__'

def post_coldoc_edit(request, NICK):
    assert slug_re.match(NICK)
    if request.method != 'POST' :
        return redirect(django.urls.reverse('ColDoc:index', kwargs={'NICK':NICK,}))
    #
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    if not request.user.has_perm('ColDocApp.change_dcoldoc'):
        logger.error('Hacking attempt',request.META)
        raise SuspiciousOperation("Permission denied")
    #
    form = ColDocForm(request.POST, instance=coldoc)
    #
    if not form.is_valid():
        return HttpResponse("Invalid form: "+repr(form.errors),status=http.HTTPStatus.BAD_REQUEST)
    form.save()
    messages.add_message(request,messages.INFO,'Changes saved')
    return index(request, NICK)


def index(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    #coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,NICK)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    c=c[0]
    #
    coldocform = None
    if request.user.is_authenticated:
        if request.user.is_staff or c.editor.filter(username=request.user.username).exists():
            coldocform = ColDocForm(instance=c)
            for a in 'nickname','root_uuid':
                coldocform.fields[a].widget.attrs['readonly'] = True
    #
    from ColDocDjango.utils import convert_latex_return_codes
    latex_error_logs = convert_latex_return_codes(c.latex_return_codes, c.nickname, c.root_uuid)
    #
    failed_blobs = map( lambda x : (x, django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':x})),
                        DMetadata.objects.exclude(latex_return_codes__exact='').values_list('uuid', flat=True))
    #
    check_tree_url = django.urls.reverse('ColDoc:check_tree', kwargs={'NICK':NICK,})
    return render(request, 'coldoc.html', {'coldoc':c,'NICK':c.nickname,
                                           'coldocform' : coldocform,
                                           'failedblobs' : failed_blobs,
                                           'check_tree_url' : check_tree_url,
                                           'latex_error_logs':latex_error_logs})

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



def check_tree(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,), status=http.HTTPStatus.NOT_FOUND)
    c=c[0]
    try:
        from ColDocDjango.helper import check_tree
        problems = check_tree(logger.warning, settings.COLDOC_SITE_ROOT, NICK)
        if problems:
            s = '<h3>Problems in tree of blobs</h3><ul>'
            for z in problems:
                s += '<li>'+ '→'.join( map(str,z)) + '</li>'
            s += '</ul>'
        else: 
            s = 'Tree is fine.'
        return HttpResponse(s)
    except Exception as e:
        logger.exception(repr(e))
        return HttpResponse("Internal error", status=http.HTTPStatus.SERVICE_UNAVAILABLE)
