import os, sys, mimetypes, http, pathlib, pickle, base64
from os.path import join as osjoin

import django
from django.forms import ModelForm


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
