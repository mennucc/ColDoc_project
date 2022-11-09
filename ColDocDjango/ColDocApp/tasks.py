import os, sys, mimetypes, http, pathlib, pickle, base64, tempfile, time, datetime
from os.path import join as osjoin

import django
from django.forms import ModelForm
from django.conf import settings
from django.core.mail import EmailMessage

import logging
logger = logging.getLogger(__name__)

from ColDoc.latex import latex_main , latex_anon, latex_tree


# https://django-background-tasks.readthedocs.io/en/latest/

from background_task import background

def latex_generic_sched(subject_prefix, cmd,*v,**k):
    ## create the real options
    options = k['options']
    assert isinstance(options, list)
    coldoc_dir, blobs_dir, coldoc_nick, url = options
    from ColDocApp.models import DColDoc
    coldoc = DColDoc.objects.filter(nickname = coldoc_nick).get()
    from UUID.views import _prepare_latex_options
    options = _prepare_latex_options(None, coldoc_dir, blobs_dir, coldoc, url)
    k['options'] = options
    ##
    if 'verbose_name' in k: del k['verbose_name']
    a = ' , '.join( ('%r=%r'%(i,j)) for i,j in k.items() )
    logger.debug('Starting scheduled %s ( %s , %s)' , cmd.__name__, ' , '.join(v), a)
    email_to = k.pop('email_to',None)
    coldoc = options.get('coldoc')
    time_ = -time.time()
    ret = cmd(*v,**k)
    time_ += time.time()
    time_ = datetime.timedelta(seconds=int(time_))
    if email_to:
        E = EmailMessage(subject=subject_prefix+str(coldoc),
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[email_to],)
        E.body = 'Run for %s, %s' %( time_ , 'success' if ret else 'failed')
        try:
            E.send()
        except:
            logger.exception('While sending email')


@background()
def latex_main_sched(*v,**k):
    return latex_generic_sched('latex whole private version of ', latex_main, *v, **k)

@background()
def latex_anon_sched(*v,**k):
    return latex_generic_sched('latex whole public version of ', latex_anon, *v, **k)

@background()
def latex_tree_sched(*v,**k):
    return latex_generic_sched('latex whole tree of blobs of ', latex_tree, *v, **k)


from background_task.models import Task, CompletedTask

class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ['verbose_name','run_at','failed_at']

class CompletedTaskForm(ModelForm):
    class Meta:
        model = CompletedTask
        fields = ['verbose_name','run_at','failed_at']

@background()
def reparse_all_sched(email_to, NICK):
    log_file = tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', prefix='reparse')
    def writelog(msg, args):
        s = msg % args # TODO how to translate?
        log_file.write(s+'\n')
    from helper import reparse_all
    reparse_all(writelog, settings.COLDOC_SITE_ROOT, NICK)
    log_file.close()
    if email_to:
        E = EmailMessage(subject='reparsing of '+NICK,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[email_to],)
        if os.path.getsize(log_file.name):
            E.body = 'Results of parsing:\n'+open(log_file.name).read()
        else:
            E.body = 'No differences in metadata were found while parsing.'
        try:
            E.send()
        except:
            logger.exception('While sending email')
            logger.warning('Reparse logs are in '+str(log_file.name))
        else:
            os.unlink(log_file.name)
