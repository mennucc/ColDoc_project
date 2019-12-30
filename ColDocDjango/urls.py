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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('UUID/', include('UUID.urls')),
]

##if False and not APACHE:
    # only for development! Apache would serve these:
  #  urlpatterns += [
   ##     {'document_root': MEDIA_ROOT}),
     #   url(r'^static/(?P<path>.*)$', django.views.static.serve,
      #   {'document_root': STATIC_ROOT}),
       # ]

urlpatterns += [
#    'cvgmt.main.views',
    #path('robots.txt', HttpResponse("", content_type="text/plain")),
    #re_path('^%s$'%GOOGLE_SITE_VERIFICATION, lambda r: HttpResponse('google-site-verification: %s' % GOOGLE_SITE_VERIFICATION,content_type='text/plain')),
    re_path(r'^$', ColDocDjango.views.main_page),
    ]



#urlpatterns  += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# must be last!
#urlpatterns += [
#    url(r'^(.*)', views.slug_page),
#    ]
