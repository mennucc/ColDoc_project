#!/usr/bin/env python3
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

COLDOC_SITE_ROOT = None
COLDOC_SRC_ROOT = None

def samefile(a,b):
    try:
        return os.path.samefile(a,b)
    except:
        return os.path.realpath(a) == os.path.realpath(b)


if True:
    a = __file__
    d = os.path.dirname(a)
    # this is standard, but we do not want it
    if  samefile(d, sys.path[0]):
        logger.info('del %r from sys.path', d)
        del sys.path[0]
    #
    if os.path.islink(a):
        COLDOC_SITE_ROOT = d
        if 'COLDOC_SITE_ROOT' in os.environ and not samefile( os.environ['COLDOC_SITE_ROOT'] , d ):
            logger.error('Environment is COLDOC_SITE_ROOT=%r but wsgi script is in %r',
                         os.environ['COLDOC_SITE_ROOT'], d)
        else:
            logger.info('setting COLDOC_SITE_ROOT=%r',d)
            os.environ['COLDOC_SITE_ROOT'] = d
        #
        a = os.readlink(a)
        a = os.path.realpath(a)
        a = os.path.dirname(a)
        pa = os.path.dirname(a)
        sd = COLDOC_SRC_ROOT = os.path.dirname(pa)
        if 'COLDOC_SRC_ROOT' in os.environ and not samefile( os.environ['COLDOC_SRC_ROOT'], sd):
            logger.error('Environment is COLDOC_SRC_ROOT=%r but wsgi script links to %r',
                         os.environ['COLDOC_SRC_ROOT'], sd)
        else:
            os.environ['COLDOC_SRC_ROOT'] = sd
            logger.info('setting COLDOC_SRC_ROOT=%r', sd)
    else:
        if 'COLDOC_SITE_ROOT' not in os.environ:
            logger.error('COLDOC_SITE_ROOT not known')
        else:
            COLDOC_SITE_ROOT = os.environ['COLDOC_SITE_ROOT']
        if 'COLDOC_SRC_ROOT' not in os.environ:
            logger.error('COLDOC_SRC_ROOT not known')
        else:
            COLDOC_SRC_ROOT = os.environ['COLDOC_SRC_ROOT']

if COLDOC_SRC_ROOT is None:
    logger.error('COLDOC_SRC_ROOT is undefined')
elif not os.path.isfile(os.path.join(COLDOC_SRC_ROOT,'ColDocDjango','manage.py') ):
    logger.error('COLDOC_SRC_ROOT does not contain `ColDocDjango/manage.py`: %r ', COLDOC_SRC_ROOT)
else:
    a = os.path.join(COLDOC_SRC_ROOT,'ColDocDjango')
    if a not in sys.path:
        logger.info('prepend %r to  sys.path',a)
        sys.path.insert(0, a)

if   sys.base_prefix != sys.prefix:
    # this triggers in virtualenvs
    a = os.path.join(sys.prefix,'bin')
    p = os.environ.get('PATH','')
    l = p.split(os.pathsep)
    if not p:
        logger.error('System path is empty??')
    else:
        p = os.pathsep + p
    if a not in l:
        logger.info('prepend %r to path %r',a, p)
        os.environ['PATH'] = a + p

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
