from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.http import HttpResponse

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

