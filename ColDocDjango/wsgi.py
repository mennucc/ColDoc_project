"""
WSGI config for ColDoc project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os, sys

if False:
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]

if True:
    os.environ['COLDOC_SITE_ROOT']=os.path.dirname(__file__)

if False:
    a = os.path.realpath(__file__)
    a = os.readlink(a)
    a = os.path.realpath(a)
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    del a

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')

application = get_wsgi_application()
