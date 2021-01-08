"""
WSGI config for ColDoc project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os, sys

import logging
logger = logging.getLogger(__name__)

if False:
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]


if True:
    a = __file__
    if os.path.islink(a):
        d = os.path.dirname(a)
        if 'COLDOC_SITE_ROOT' in os.environ and not os.path.samefile( os.environ['COLDOC_SITE_ROOT'] , d ):
            logger.error('Environment is COLDOC_SITE_ROOT=%r but wsgi script is in %r',
                         os.environ['COLDOC_SITE_ROOT'], d)
        else:
            logger.info('COLDOC_SITE_ROOT=%r',d)
            os.environ['COLDOC_SITE_ROOT'] = d
        a = os.readlink(a)
        a = os.path.realpath(a)
        a = os.path.dirname(a)
        sd = os.path.dirname(a)
        if 'COLDOC_SRC_ROOT' in os.environ and not  os.path.samefile( os.environ['COLDOC_SRC_ROOT'], sd):
            logger.error('Environment is COLDOC_SRC_ROOT=%r but wsgi script links to %r',
                         os.environ['COLDOC_SRC_ROOT'], sd)
        else:
            os.environ['COLDOC_SRC_ROOT'] = sd
            logger.info('COLDOC_SRC_ROOT=%r', sd)
        if sd not in sys.path:
            sys.path.insert(0, sd)
    else:
        if 'COLDOC_SITE_ROOT' not in os.environ:
            logger.error('COLDOC_SITE_ROOT not known')
        if 'COLDOC_SRC_ROOT' not in os.environ:
            logger.error('COLDOC_SRC_ROOT not known')
        else:
            sys.path.insert(0, os.environ['COLDOC_SRC_ROOT'])

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')

application = get_wsgi_application()
