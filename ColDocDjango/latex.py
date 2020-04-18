#!/usr/bin/env python3

"""See ColDocDjango/latex.py
"""

import os, sys, shutil, subprocess, argparse, json

from os.path import join as osjoin

if __name__ == '__main__':
    for j in ('','.'):
        if j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)

import ColDoc.latex


def main(argv):
    # parse arguments
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser = ColDoc.latex.prepare_parser()
    parser.add_argument('--coldoc-nick',type=str,\
                        help='nickname for the coldoc document',
                        required=True)
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    parser.add_argument('--url-UUID',type=str,\
                        help='URL of the website that will show the UUIDs, used by my \\uuid macro in PDF')
    args = parser.parse_args(argv[1:])
    #
    COLDOC_SITE_ROOT = args.coldoc_site_root
    assert os.path.isdir(COLDOC_SITE_ROOT), COLDOC_SITE_ROOT
    #
    args.blobs_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',args.coldoc_nick,'blobs')
    assert os.path.isdir(args.blobs_dir) , args.blobs_dir
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',args.coldoc_nick)
    # read options
    options = {}
    #
    a = osjoin(COLDOC_SITE_ROOT,'config.ini')
    import configparser
    config = configparser.ConfigParser()
    config.read([a])
    for k in 'server_url', 'hostname':
        options[k] = config['django'][k]
    #
    a = osjoin(coldoc_dir, 'coldoc.json')
    if os.path.isfile( a ):
        coldoc = json.load(open(a))
        options.update(coldoc['fields'])
        logger.debug('From %r options %r',a,options)
    else:
        logger.debug('No %r',a)
    #
    #a = osjoin(blobs_dir, '.blob_inator-args.json')
    #if os.path.isfile( a ):
    #    blob_inator_args = json.load(open(a))
    #    assert isinstance(blob_inator_args,dict)
    #    options.update(blob_inator_args)
    #    logger.debug('From %r options %r',a,options)
    #else:
    #    logger.debug('No %r',a)
    #
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
    import django
    django.setup()
    import ColDocDjango.ColDocApp.models as coldocapp_models
    import ColDocDjango.UUID.models as  blob_models
    from ColDocDjango.transform import squash_helper_ref
    #
    matches = list(coldocapp_models.DColDoc.objects.filter(nickname = args.coldoc_nick))
    if len(matches) > 1 :
        raise ValueError("Too many ColDoc with nick %r." % (args.coldoc_nick,) )
    #
    options['coldoc'] = coldoc = matches[0]
    def foobar(*v, **k):
        " helper factory"
        return squash_helper_ref(coldoc, *v, **k)
    options["squash_helper"] = foobar
    return ColDoc.latex.main_by_args(args,options)


if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)