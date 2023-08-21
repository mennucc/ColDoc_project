import os, sys, mimetypes, http, pathlib, pickle, base64, functools, copy, re, hashlib
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
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from django.utils.translation import gettext, gettext_lazy, gettext_noop
if django.VERSION[0] >= 4 :
    _ = gettext_lazy
else:
    # in django 3 you cannot concatenate strings to lazy-strings
    _ = gettext



###################

import coldoc_tasks.task_utils


def _fork_class_callback(f):
    if f.fork_type in ('simple',) and  settings.CLOSE_CONNECTION_ON_FORK:
        logger.critical('Using %s forks for subprocesses , is incompatible with certain databases',
                        f.fork_type)

fork_class_default = \
    coldoc_tasks.task_utils.choose_best_fork_class(getattr(settings,'COLDOC_TASKS_INFOFILE',None),
                                                   getattr(settings,'COLDOC_TASKS_CELERYCONFIG',None),
                                                   callback=_fork_class_callback)

################

import ColDoc.utils, ColDocDjango
from ColDoc.utils import slug_re, slugp_re, langc_re , lang_re, uuid_valid_symbols,  get_blobinator_args
from .models import DColDoc
from UUID.models import DMetadata, ExtraMetadata
from UUID import views as UUIDviews
from ColDocDjango.transform import squash_helper_ref
from ColDocApp import text_catalog

from ColDocDjango.users import user_has_perm , UUID_view_view , UUID_view_blob #, UUID_download  #, user_has_perm_uuid_blob
from ColDocDjango.utils import check_login_timeout, build_hreflang_links

from ColDoc.utils import parse_index_arg, re_index_lang
from ColDoc.utils import iso3lang2word as iso3lang2word_untranslated

def iso3lang2word(*v , **k):
    return gettext_lazy(iso3lang2word_untranslated(*v, **k))


class ColDocForm(ModelForm):
    class Meta:
        model = DColDoc
        exclude = []
        exclude = ['headline']
        fields = '__all__'

def post_coldoc_edit(request, NICK):
    if not slug_re.match(NICK) : raise SuspiciousOperation("Permission denied")
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
        messages.add_message(request,messages.ERROR,repr(form.errors))
        # https://stackoverflow.com/a/70625499/5058564
        k = 'class'
        for field in form.errors:
            a = form[field].field.widget.attrs
            a[k] = a.get(k,'') + ' border-warning'
        # FIXME should add `#settings` at the end of the URL
        return index(request, NICK, coldocform=form)
    form.save()
    messages.add_message(request,messages.INFO,'Changes saved')
    return index(request, NICK)


def index(request, NICK, coldocform=None):
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
    assert coldocform is None or isinstance(coldocform, ColDocForm)
    if request.user.has_perm('ColDocApp.view_dcoldoc'):
        if coldocform is None:
            coldocform = ColDocForm(instance=coldoc)
        coldocform.htmlid = 'id_coldocform'
        for a in 'nickname','root_uuid':
            coldocform.fields[a].widget.attrs['readonly'] = True
    else:
        coldocform = None
    #
    latex_error_logs = []
    failed_blobs = []
    tasks = []
    completed_tasks = []
    if request.user.is_editor:
        from ColDocDjango.utils import convert_latex_return_codes, latex_error_fix_line_numbers
        latex_error_logs = convert_latex_return_codes(coldoc.latex_return_codes, coldoc.nickname, coldoc.root_uuid)
        load_uuid = functools.partial(DMetadata.load_by_uuid, coldoc=coldoc)
        latex_error_logs = latex_error_fix_line_numbers(blobs_dir, anon_dir, coldoc.root_uuid, latex_error_logs, load_uuid, prefix='main')
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
    if not slug_re.match(NICK) : raise SuspiciousOperation("Permission denied")
    # in case the user login did timeout
    check_login_timeout(request, NICK)
    #
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
    if settings.USE_BACKGROUND_TASKS:
        url = django.urls.reverse('UUID:index', kwargs={'NICK':coldoc.nickname,'UUID':'000'})[:-4]
        url = request.build_absolute_uri(url)
        # hack: in this case 'options' is a list not a dict
        # and _prepare_latex_options() will be called in the task
        options = [coldoc_dir, blobs_dir, coldoc.nickname, url]
        # the fork_class cannot be passed to background tasks
        fork_class = None
    else:
        from UUID.views import _prepare_latex_options
        options = _prepare_latex_options(request, coldoc_dir, blobs_dir, coldoc)
        fork_class = fork_class_default
    #
    ret = False
    if typ_ == 'tree':
        ret = latex_tree_sched(blobs_dir, uuid=coldoc.root_uuid, options=options, verbose_name="latex_tree",
                               email_to=request.user.email, fork_class=fork_class)
    elif typ_ == 'main':
        ret = latex_main_sched(blobs_dir, uuid=coldoc.root_uuid, options=options, access='private', verbose_name="latex_main:private",
                               fork_class=fork_class,
                               email_to=request.user.email)
    else:
        ret = latex_anon_sched(coldoc_dir, uuid=coldoc.root_uuid, options=options, access='public', verbose_name="latex_main:public",
                               fork_class=fork_class,
                               email_to=request.user.email)
    if settings.USE_BACKGROUND_TASKS:
        messages.add_message(request,messages.INFO,'Compilation scheduled for '+typ_)
    elif ret:
        messages.add_message(request,messages.INFO,'Compilation finished for '+typ_)
    else:
        messages.add_message(request,messages.WARNING,'Compilation failed for '+typ_)
    return redirect(django.urls.reverse('ColDoc:index',kwargs={'NICK':NICK,}))

def reparse(request, NICK):
    if not slug_re.match(NICK) : raise SuspiciousOperation("Permission denied")
    # in case the user login did timeout
    check_login_timeout(request, NICK)
    #
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
        def writelog(msg, args):
            s = _(msg) % args
            messages.add_message(request,messages.INFO,s)
        reparse_all(writelog, settings.COLDOC_SITE_ROOT, NICK)
        messages.add_message(request,messages.INFO,'Reparsing done')
    return redirect(django.urls.reverse('ColDoc:index',kwargs={'NICK':NICK,}))


def html(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    return UUIDviews.view_(request, NICK, True, '_html', None, subpath, prefix='main', expandbuttons = False)

@xframe_options_sameorigin
def pdf(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    return UUIDviews.view_(request, NICK, True, '.pdf', None, subpath, prefix='main')

def pdfframe(request, NICK, subpath=None):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    #
    r = UUIDviews.view_mul(request, NICK, True, '.pdf', None, subpath, prefix='main')
    # some error
    if not isinstance(r,tuple):
        return r
    #
    filename, ACCESS, _content_type, _content_encoding, _view_ext, coldoc, rootuuid, lang, child_uuid = r
    #
    hreflanglinks = build_hreflang_links(request.build_absolute_uri(request.path),
                                         None,coldoc.get_languages(),None)
    #
    FILENAME = os.path.basename(filename)
    UUID = coldoc.root_uuid
    view_md5 = hashlib.md5(open(filename,'rb').read()).hexdigest()
    # use effective language
    a = [ 'lang=%s' % lang ]
    #
    uuid = request.GET.get('uuid')
    if uuid :
        if not uuid_valid_symbols.match(uuid):
            raise SuspiciousOperation("Invalid uuid %r in query." % (uuid,))
        # this is not really used
        a.append( 'uuid=%s' % uuid )
    #
    if ACCESS:
        a.append( 'access=%s' % ACCESS )
    #
    pdfurl = django.urls.reverse('ColDoc:pdf', kwargs={'NICK':NICK,})
    pdfurl += '?' + '&'.join(a)
    # but this is used to jump the uuid
    if uuid:
        pdfurl += "#UUID:%s" % uuid
    LANGUAGE = iso3lang2word(lang)
    #
    pdfframeurl = django.urls.reverse('ColDoc:pdfframe', kwargs={'NICK':NICK,})
    LANGUAGES = []
    L = coldoc.get_languages()
    if len(L) > 1:
        for l in L:
            a[0] = 'lang=%s' % l
            LANGUAGES.append( (iso3lang2word(l),
                               pdfframeurl + '?' + '&'.join(a)  +  '#titlebeforepdf' ) )
    del a
    MAIN_CONTAINER_CLASS = "container-fluid"
    return render(request, 'pdfframe.html', locals() )


def search_text_list(request, coldoc, searchtoken):
    NICK = coldoc.nickname
    coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs', NICK)
    blobs_dir = osjoin(coldoc_dir,'blobs')
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    accept_lang = ColDocDjango.utils.request_accept_language(accept, cookie)
    text_list = []
    Clangs = copy.copy(coldoc.get_languages())
    searchtoken = searchtoken.lower()
    searchtoken = re.sub('\s+',' ',searchtoken)
    user = request.user
    for result in text_catalog.search_text_catalog(searchtoken, coldoc):
        uuid = result.uuid
        blob = DMetadata.objects.filter(uuid=uuid).get()
        user.associate_coldoc_blob_for_has_perm(coldoc, blob)
        if user.has_perm(UUID_view_view):
            lang = result.lang 
            link = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':uuid}) + '?lang=' + lang
            text_list.append((blob.uuid, lang, link, result.text)) 
    return text_list

def bookindex(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    user = request.user
    user.associate_coldoc_blob_for_has_perm(coldoc, None)
    ## permissions
    user_can_view = lambda extra :  user.has_perm (  UUID_view_view ,  extra.blob )
    #user_can_blob = lambda extra :  user.has_perm (  UUID_view_blob ,  extra.blob )
    
    i_ = ExtraMetadata.objects.filter(Q(key__contains='M_index') & 
                                              Q(blob__coldoc=coldoc))
    i_ = filter(user_can_view, i_)
    #
    indexes_by_lang = {}
    for E in i_:
        try:
            l = re_index_lang.findall(E.key)
            language = l[0] if l else ''
            key, see, value, text_class = parse_index_arg(E.value)
        except ValueError:
            continue
        L = indexes_by_lang.setdefault(language, {})
        lis = L.setdefault(key, [])
        html = ( _(see) + ' <span class="font-italic">' + value + '</span>') if (see and value) else E.blob.uuid
        lis.append( (E.blob.uuid, html, text_class) )
    nolanguage = _("Any language") if (len(indexes_by_lang.keys())>1) else ''
    index = []
    for language in indexes_by_lang:
        L = indexes_by_lang[language]
        I = []
        for k,vv in L.items():
            I.append((k,vv))
        I.sort()
        index.append( (iso3lang2word(language) if language else nolanguage,
                       I) )
    #
    return render(request, 'bookindex.html',
                  {'coldoc':coldoc, 'NICK':coldoc.nickname,
                   'index':index,
                   })

def search(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    if request.method == 'POST' :
        searchtoken = request.POST.get('searchtoken')
        if searchtoken is None:
            logger.error('Search POST with not "searchtoken" : hacking attemp?')
            raise SuspiciousOperation("Search POST with not 'searchtoken'  ...")
    else:
        assert request.method == 'GET'
        searchtoken = request.GET.get('searchtoken')
        if searchtoken is None:
            # this happens when the user logs in or logs out while on the search page
            return redirect(django.urls.reverse('ColDoc:index',
                                                kwargs={'NICK':NICK,})) 
        #return HttpResponse("Method %r not allowed"%(request.method,),status=http.HTTPStatus.BAD_REQUEST)
    #
    searchtoken = searchtoken.strip()
    if len(searchtoken) <= 1:
        messages.add_message(request, messages.WARNING, "Search key is too short.")
        return index(request, NICK)
    #
    coldoc = DColDoc.objects.filter(nickname = NICK).get()
    #
    user = request.user
    user.associate_coldoc_blob_for_has_perm(coldoc, None)
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
    ## permissions
    user_can_view = lambda extra :  user.has_perm (  UUID_view_view ,  extra.blob )
    user_can_blob = lambda extra :  user.has_perm (  UUID_view_blob ,  extra.blob )
    #
    
    def is_author_(extra, username_):
        return extra.blob.author.filter(username = username_).exists()
    is_author = functools.partial(is_author_, username_ = request.user.username)
    #
    if True :
        i_ = ExtraMetadata.objects.filter(Q(key__contains='M_index') & 
                                                  Q(blob__coldoc=coldoc) &
                                                  Q(value__contains=searchtoken))
        index_list = []
        for E in filter(user_can_view, i_):
            try:
                l = re_index_lang.findall(E.key)
                language = ('/' + l[0]) if l else ''
                key, see, value, text_class = parse_index_arg(E.value)
            except ValueError:
                continue
            html = (',' +  _(see) + ' <span class="font-italic">' + value + '</span>') if (see and value) else ''
            index_list.append( (language, key, E.blob.uuid, html, text_class ) )
        index_list.sort()
    else:
        index_list = []
    #
    if request.user.is_authenticated :
        label_list = ExtraMetadata.objects.filter(Q(key__endswith='M_label') & 
                                                  Q(blob__coldoc=coldoc) &
                                                  Q(value__contains=searchtoken))
        ref_list = ExtraMetadata.objects.filter((Q(key__endswith='M_ref') |
                                                 Q(key__endswith='M_eqref') |
                                                 Q(key__endswith='M_pageref') )   & 
                                                Q(blob__coldoc=coldoc) &
                                                Q(value__contains=searchtoken))
        label_list = list(filter(user_can_blob, label_list))
        ref_list   = list(filter(user_can_blob, ref_list))
    else:
        label_list = ref_list = []
    #
    meta_list = []
    if request.user.is_authenticated :
        blobs_dir = osjoin(settings.COLDOC_SITE_ROOT,'coldocs',NICK,'blobs')
        blobinator_args = get_blobinator_args(blobs_dir)
        for j in blobinator_args["metadata_command"]:
            if j not in ('label','ref','eqref','pageref','index'):
                meta_list += list(ExtraMetadata.objects.filter(Q(key__endswith=('M_'+j)) & 
                                                      Q(blob__coldoc=coldoc) &
                                                      Q(value__contains=searchtoken)))
        meta_list = list(filter(user_can_blob, meta_list))
    # search in text
    text_list = search_text_list(request, coldoc, searchtoken)
    # shortcut
    if len(uuid_list)==1 and not label_list and not index_list and not ref_list and not meta_list and not text_list:
        return redirect(django.urls.reverse('UUID:index',
                                            kwargs={'NICK':NICK,'UUID':uuid_list[0].uuid}))
    
    return render(request, 'search.html',
                  {'coldoc':coldoc, 'NICK':coldoc.nickname, 'maybe_uuid':maybe_uuid,
                   'uuid_list':uuid_list,'label_list':label_list,'ref_list':ref_list,
                   'index_list':index_list, 'meta_list':meta_list,
                   'text_list': text_list, 'searchpreset' : searchtoken,
                   })



def check_tree(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,), status=http.HTTPStatus.BAD_REQUEST)
    c = DColDoc.objects.filter(nickname = NICK).get()
    request.user.associate_coldoc_blob_for_has_perm(c, None)
    # maybe session timed out
    if not request.user.is_authenticated:
        return HttpResponse("Please login again.", status=http.HTTPStatus.FORBIDDEN)
    #
    if not request.user.is_editor:
        raise SuspiciousOperation("Permission denied")
    #
    try:
        from helper import check_tree
        def warn(s,a):
            pass 
            ## avoid clobbering logs
            #logger.warning(s % a)
        problems = check_tree(warn, settings.COLDOC_SITE_ROOT, NICK)
    except Exception:
        logger.exception('on check_tree')
        return HttpResponse("Internal error on check_tree", status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    if problems:
        s = '<h3>' + _('Problems in tree of blobs') + '</h3><ul>'
        disconnected = set()
        try:
            for problem in problems:
                if problem[0] == 'DISCONNECTED':
                    disconnected.add(problem[1])
        except:
            logger.exception('when scanning list of problems')
        for problem in problems:
            try:
                code, uuid, msg, args = problem
                try:
                    desc = _(msg) % args
                except:
                    logger.exception('when formatting msg %r args %r',msg,args)
                    desc = repr((msg,args))
                if uuid in disconnected:
                    s += '<li class="font-italic font-weight-light" >'
                else:
                    s += '<li>'
                if isinstance(uuid,str):
                    url = django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':uuid})
                    s += ('<a href="%s">'%(url,)) + uuid + '</a> →' + desc + '</li>'
                elif uuid:
                    s += repr(uuid) + ' →' + desc + '</li>'
                else:
                    s += desc + '</li>'
            except Exception as e:
                logger.exception('when formatting %r',problem)
                s += '<li>' + repr(problem) + '</li>\n'
        s += '</ul>'
    else: 
        s = _('Tree is fine.')
    return HttpResponse(s)
