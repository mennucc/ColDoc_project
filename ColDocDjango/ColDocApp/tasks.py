import os, sys, mimetypes, http, pathlib, pickle, base64, tempfile
from os.path import join as osjoin

import django
from django.forms import ModelForm
from django.conf import settings
from django.core.mail import EmailMessage

import logging
logger = logging.getLogger(__name__)

from ColDoc.latex import latex_main #as latex_main__


# https://django-background-tasks.readthedocs.io/en/latest/

from background_task import background

@background()
def latex_main_sched(*v,**k):
    options = k['options']
    if isinstance(options, (str,bytes) ):
        # base64 accepts both bytes and str
        options = pickle.loads(base64.b64decode(options))
    k['options'] = options
    if 'verbose_name' in k: del k['verbose_name']
    a = ' , '.join( ('%r=%r'%(i,j)) for i,j in k.items() )
    logger.debug('Starting scheduled latex_main ( %s , %s)' , ' , '.join(v), a)
    return latex_main(*v,**k)


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
    def writelog(s):
        log_file.write(s+'\n')
    from ColDocDjango.helper import reparse_all
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
