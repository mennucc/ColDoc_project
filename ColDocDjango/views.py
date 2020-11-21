import re, http

number_re = re.compile(r'^[0-9]+\Z')

import logging
logger = logging.getLogger(__name__)

from django.contrib.auth.validators import UnicodeUsernameValidator
valid_user_re = UnicodeUsernameValidator().regex

import django
from django import forms
from django.template.loader import render_to_string
from django.core.exceptions import SuspiciousOperation
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages
from django import forms
from django.contrib.auth import get_user_model

UsMo = get_user_model()

from ColDoc.utils import slug_re, slugp_re

from ColDocDjango.ColDocApp.models import DColDoc

def main_page(request):
    c = {'DColDocs':DColDoc.objects.all()} #default_context_for(request)
    return render(request, 'index.html', c)


def robots_page(request):
    return HttpResponse("""User-agent: *
Disallow: /login/
Disallow: /logout/
Disallow: /accounts/
Disallow: /admin/
Disallow: /wallet/
""", content_type="text/plain")

