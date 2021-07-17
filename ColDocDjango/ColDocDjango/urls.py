"""ColDoc URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import django
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf.urls.static import static
from django.http import HttpResponse

import ColDocDjango.views
from django.conf import settings
config = settings.COLDOC_SITE_CONFIG

import django.contrib.auth
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path('robots.txt', ColDocDjango.views.robots_page),
    path('admin/', admin.site.urls),
    path('UUID/', include('UUID.urls')),
    path('CD/', include('ColDocApp.urls')),
    ]

if settings.USE_WALLET:
    urlpatterns += [
        path('wallet/', include('wallet.urls')),
        ]

if settings.USE_SELECT2:
    urlpatterns += [
        path('select2/', include('django_select2.urls')),
        ]

if settings.USE_ALLAUTH:
    urlpatterns += [
        path('accounts/', include('allauth.urls')),
        ]
else:
    urlpatterns += [
    path('login/', 
         LoginView.as_view(
             template_name='admin/login.html',
             extra_context={
                 'title': 'Login',
                 'site_title': config['DEFAULT']['site_name'],
                 'site_header': config['DEFAULT']['site_name']+' : Login'}),
         name="account_login"),
    path('logout/',  LogoutView.as_view(), name="account_logout"),
]

from ColDocDjango import views

urlpatterns += [
    re_path(r'^$', ColDocDjango.views.main_page, name='index'),
    path('user', views.user, name='user'),
    path('send_email', views.send_email, name='send_email'),
    ]

if isinstance(settings.GOOGLE_SITE_VERIFICATION,str):
    urlpatterns += [
        path(settings.GOOGLE_SITE_VERIFICATION, lambda r: \
             HttpResponse('google-site-verification: %s' % settings.GOOGLE_SITE_VERIFICATION,content_type='text/plain')),
        ]
