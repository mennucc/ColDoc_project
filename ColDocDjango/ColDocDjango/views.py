import re, http

number_re = re.compile(r'^[0-9]+\Z')

import logging
logger = logging.getLogger(__name__)

from django.contrib.auth.validators import UnicodeUsernameValidator
valid_user_re = UnicodeUsernameValidator().regex

import django
from django import forms
#from django.template.loader import render_to_string
#from django.core.exceptions import SuspiciousOperation
from django.shortcuts import get_object_or_404, render, redirect
#from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages
from django import forms
from django.contrib.auth import get_user_model

UsMo = get_user_model()

#from ColDoc.utils import slug_re, slugp_re
from ColDocDjango.utils import get_email_for_user

from ColDocApp.models import DColDoc

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



class Email_Form(forms.Form):
    subject = forms.CharField(label='Subject',max_length=255, required=True,)
    message = forms.CharField(
        required=True,
        widget=forms.Textarea
    )
    email_from = forms.CharField(widget=forms.HiddenInput, required=True,)
    email_to   = forms.CharField(widget=forms.HiddenInput, required=True,)



def user(request):
    if request.user.is_anonymous:
        return HttpResponse("Please login.", status=http.HTTPStatus.UNAUTHORIZED)
    #
    nr = request.GET.get('nr')
    if not ( nr is None or number_re.match(nr) ) : return (HttpResponse('Bad "nr"', status=http.HTTPStatus.BAD_REQUEST))
    username = request.GET.get('username')
    if not ( username is None or valid_user_re.match(username) ) : return (HttpResponse('Bad "username"', status=http.HTTPStatus.BAD_REQUEST))
    #
    if username is None and nr is None:
        username = request.user.username
    #
    O = UsMo.objects
    if username:  O = O.filter(username=username)
    if nr:  O = O.filter(id=nr)
    try:
        thatuser = O.get()
    except UsMo.DoesNotExist:
        return HttpResponse("No such user", status=http.HTTPStatus.NOT_FOUND)
    #
    from_email = get_email_for_user(request.user)
    to_email   = get_email_for_user(thatuser)
    #
    if from_email and to_email and request.user.id != thatuser.id :
        email_form = Email_Form(initial={ 'email_to' : to_email , 'email_from' : from_email })
    else:
        email_form = None
    return render(request, 'user.html', locals())

def send_email(request):
    if request.user.is_anonymous:
        return HttpResponse("Please login.", status=http.HTTPStatus.UNAUTHORIZED)
    if request.method != 'POST' :
        return redirect(django.urls.reverse('index'))
    email_form = Email_Form(request.POST)
    if not email_form.is_valid():
        return HttpResponse("Invalid form: "+repr(email_form.errors),status=http.HTTPStatus.BAD_REQUEST)
    #
    email_to   = email_form.cleaned_data['email_to']
    email_from = email_form.cleaned_data['email_from']
    a = get_email_for_user(request.user)
    if not email_from:
        return HttpResponse("No email for %r." % (request.user,), status=http.HTTPStatus.BAD_REQUEST)
    assert a == email_from
    #
    from django.core.mail import EmailMessage
    E = EmailMessage(subject = email_form.cleaned_data['subject'],
                     from_email = email_from,
                     to=[ email_to, ],)
    E.body = email_form.cleaned_data['message']
    try:
        E.send()
    except:
        logger.exception('email failed')
        messages.add_message(request, messages.WARNING, 'Failed to send email')
    else:
        messages.add_message(request, messages.INFO, 'Email sent to %s'%(email_to,))
    return redirect(django.urls.reverse('index'))
