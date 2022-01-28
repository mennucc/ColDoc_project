import os, sys, mimetypes, http, pathlib, pickle, base64
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
from django.core.exceptions import SuspiciousOperation

import ColDoc.utils, ColDocDjango

from ColDoc.utils import slug_re, get_blobinator_args

from django.conf import settings

from UUID import views as UUIDviews

from django.shortcuts import get_object_or_404, render

from .models import DColDoc

from UUID.models import DMetadata, ExtraMetadata

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
        logger.error('Hacking attempt %r',request.META)
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
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    anon_dir = osjoin(coldoc_dir,'anon')
    try:
        coldoc = DColDoc.objects.filter(nickname = NICK).get()
    except DColDoc.DoesNotExist:
        return HttpResponse("No such ColDoc %r.\n" % (NICK,) , status=http.HTTPStatus.NOT_FOUND)
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    #
    if request.user.has_perm('UUID.view_view') :
        whole_button_class = 'btn-outline-success'
    else:
        whole_button_class = 'btn-outline-primary'
    #
    coldocform = None
    if request.user.has_perm('ColDocApp.view_dcoldoc'):
        coldocform = ColDocForm(instance=coldoc)
        coldocform.htmlid = 'id_coldocform'
        for a in 'nickname','root_uuid':
            coldocform.fields[a].widget.attrs['readonly'] = True
    #
    latex_error_logs = []
    failed_blobs = []
    tasks = []
    completed_tasks = []
    if request.user.is_editor:
        from ColDocDjango.utils import convert_latex_return_codes
        latex_error_logs = convert_latex_return_codes(coldoc.latex_return_codes, coldoc.nickname, coldoc.root_uuid)
        #
        a = []
        try:
            for e_prog, e_language, e_access, e_extension, e_link, useless in latex_error_logs:
                _dir = blobs_dir if e_access == 'private' else anon_dir
                uuid_line_err = ColDoc.utils.parse_latex_log(_dir, coldoc.root_uuid, e_language, e_extension, prefix='main')
                a.append( (e_prog, e_language, e_access, e_extension, e_link, uuid_line_err) )
        except:
            logger.exception('while reparsing latex error logs')
        else:
            latex_error_logs = a
        #
        failed_blobs = map( lambda x : (x, django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':x})),
                            DMetadata.objects.filter(coldoc=coldoc).exclude(latex_return_codes__exact='').values_list('uuid', flat=True))
        #
        if Task is not None:
            tasks = [ TaskForm(instance=j, prefix=j.id) for j in Task.objects.all() ]
            completed_tasks = [ CompletedTaskForm(instance=j, prefix=j.id) for j in CompletedTask.objects.all() ]
        #
    check_tree_url = django.urls.reverse('ColDoc:check_tree', kwargs={'NICK':NICK,})
    return render(request, 'coldoc.html', {'coldoc':coldoc,'NICK':coldoc.nickname,
                                           'coldocform' : coldocform,
                                           'failedblobs' : failed_blobs,
                                           'check_tree_url' : check_tree_url,
                                           'whole_button_class' : whole_button_class,
                                           'tasks' : tasks, 'completed_tasks' : completed_tasks,
                                           'latex_error_logs':latex_error_logs})

##################

from ColDoc.latex import latex_main, latex_anon, latex_tree

if settings.USE_BACKGROUND_TASKS:
    from .tasks import latex_main_sched, latex_anon_sched, latex_tree_sched, Task, CompletedTask, TaskForm, CompletedTaskForm
    #
else:
    Task = CompletedTask = None
    latex_main_sched = latex_main
    latex_anon_sched = latex_anon
    latex_tree_sched = latex_tree



def latex(request, NICK):
    assert slug_re.match(NICK)
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    if not request.user.is_editor:
        raise SuspiciousOperation("Permission denied")
    #
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    if not os.path.isdir(blobs_dir):
        raise SuspiciousOperation("No blobs for this ColDoc %r.\n" % (NICK,))    
    #
    q = request.GET
    typ_ = q.get('type')
    if typ_ not in ('main','anon','tree'):
        messages.add_message(request,messages.WARNING,'Wrong request')
        return index(request, NICK)
    #
    assert slug_re.match(typ_)
    #
    from ColDoc.latex import prepare_options_for_latex
    options = {} # prepare_options_for_latex() will be called by latex_main
    #
    url = django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':'000'})[:-4]
    url = request.build_absolute_uri(url)
    # used for PDF
    options['url_UUID'] = url
    options['coldoc'] = coldoc
    options['metadata_class'] = DMetadata
    # used to dedup plastex stuff
    options['coldoc_site_root']  = settings.COLDOC_SITE_ROOT
    options['dedup_root'] = settings.DEDUP_ROOT
    options['dedup_url'] = settings.DEDUP_URL
    # needed by `latex_tree`
    if typ_ == 'tree':
        import functools
        from ColDocDjango.transform import squash_helper_ref
        options["squash_helper"] =  functools.partial(squash_helper_ref, coldoc)
    # this signals `latex_main` to run `prepare_options_for_latex()` 
    options['coldoc_dir'] = coldoc_dir
    options = base64.b64encode(pickle.dumps(options)).decode()
    #
    ret = False
    if typ_ == 'tree':
        ret = latex_tree_sched(blobs_dir, uuid=coldoc.root_uuid, options=options, verbose_name="latex_tree", email_to=request.user.email)
    elif typ_ == 'main':
        ret = latex_main_sched(blobs_dir, uuid=coldoc.root_uuid, options=options, access='private', verbose_name="latex_main:private", email_to=request.user.email)
    else:
        ret = latex_anon_sched(coldoc_dir, uuid=coldoc.root_uuid, options=options, access='public', verbose_name="latex_main:public", email_to=request.user.email)
    if settings.USE_BACKGROUND_TASKS:
        messages.add_message(request,messages.INFO,'Compilation scheduled for '+typ_)
    elif ret:
        messages.add_message(request,messages.INFO,'Compilation finished for '+typ_)
    else:
        messages.add_message(request,messages.WARNING,'Compilation failed for '+typ_)
    return redirect(django.urls.reverse('ColDoc:index',kwargs={'NICK':NICK,}))

def reparse(request, NICK):
    assert slug_re.match(NICK)
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    request.user.associate_coldoc_blob_for_has_perm(coldoc, None)
    if not request.user.is_editor:
        raise SuspiciousOperation("Permission denied")
    #
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    if not os.path.isdir(blobs_dir):
        raise SuspiciousOperation("No blobs for this ColDoc %r.\n" % (NICK,))
    #
    if settings.USE_BACKGROUND_TASKS:
        from .tasks import reparse_all_sched
        reparse_all_sched(request.user.email, NICK, verbose_name='reparse')
        messages.add_message(request,messages.INFO,'Reparsing scheduled')
        if request.user.email:
            messages.add_message(request,messages.INFO,'Reparsing results will be sent to '+str(request.user.email))
    else:
        from helper import reparse_all
        def writelog(s):
            messages.add_message(request,messages.INFO,s)
        reparse_all(writelog, settings.COLDOC_SITE_ROOT, NICK)
        messages.add_message(request,messages.INFO,'Reparsing done')
    return redirect(django.urls.reverse('ColDoc:index',kwargs={'NICK':NICK,}))


def html(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = DColDoc.objects.filter(nickname = NICK).get()
    return UUIDviews.view_(request, c, c.root_uuid, '_html', None, subpath, prefix='main')

def pdf(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = DColDoc.objects.filter(nickname = NICK).get()
    return UUIDviews.view_(request, c, c.root_uuid, '.pdf', None, subpath, prefix='main')

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
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
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
    #
    meta_list = []
    if request.user.is_authenticated and coldoc.anonymous_can_view :
        # FIXME , would like to use `has_perm('UUID.view_view')`
        # but this currently works only on a per-blob basis:
        # so we should filter this list accordingly
        blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
        blobinator_args = get_blobinator_args(blobs_dir)
        for j in blobinator_args["metadata_command"]:
            if j not in ('label','ref','eqref','pageref','index'):
                meta_list += list(ExtraMetadata.objects.filter(Q(key__endswith=('M_'+j)) & 
                                                      Q(blob__coldoc=coldoc) &
                                                      Q(value__contains=searchtoken)))
    # TODO search in text
    # shortcut
    if len(uuid_list)==1 and not label_list and not index_list and not ref_list and not meta_list:
        return redirect(django.urls.reverse('UUID:index',
                                            kwargs={'NICK':NICK,'UUID':uuid_list[0].uuid}))
    
    return render(request, 'search.html',
                  {'coldoc':coldoc, 'NICK':coldoc.nickname, 'maybe_uuid':maybe_uuid,
                   'uuid_list':uuid_list,'label_list':label_list,'ref_list':ref_list,
                   'index_list':index_list, 'meta_list':meta_list,
                   })



def check_tree(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = DColDoc.objects.filter(nickname = NICK).get()
    try:
        from helper import check_tree
        problems = check_tree(logger.warning, settings.COLDOC_SITE_ROOT, NICK)
        if problems:
            s = '<h3>Problems in tree of blobs</h3><ul>'
            for code, uuid, desc in problems:
                if isinstance(uuid,str):
                    url = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':uuid})
                    s += ('<li><a href="%s">'%(url,)) + uuid + '</a> →' + desc + '</li>'
                elif uuid:
                    s += '<li>' + repr(uuid) + ' →' + desc + '</li>'
                else:
                    s += '<li>' + desc + '</li>'
            s += '</ul>'
        else: 
            s = 'Tree is fine.'
        return HttpResponse(s)
    except Exception as e:
        logger.exception(repr(e))
        return HttpResponse("Internal error", status=http.HTTPStatus.SERVICE_UNAVAILABLE)
