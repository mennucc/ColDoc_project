import os, sys, mimetypes
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

import django
from django.shortcuts import render
from django.http import HttpResponse, QueryDict

from django.views.decorators.clickjacking import xframe_options_sameorigin

import ColDoc.utils, ColDocDjango

from ColDoc.utils import slug_re

from ColDocDjango import settings

from django.shortcuts import get_object_or_404, render

from .models import DColDoc

def index(request, NICK):
    if not slug_re.match(NICK):
        return HttpResponse("Invalid ColDoc %r." % (NICK,))
    #coldoc_dir = osjoin(settings.COLDOC_SITE_ROOT,NICK)
    c = list(DColDoc.objects.filter(nickname = NICK))
    if not c:
        return HttpResponse("No such ColDoc %r." % (NICK,))
    c=c[0]
    return render(request, 'coldoc.html', {'coldoc':c,})
