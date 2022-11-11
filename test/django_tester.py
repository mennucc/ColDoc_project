#!/usr/bin/env python3

"""This interface to Django is used by the `Makefile`;
 this tool performs some actions on the test Django site.
 Possible commands:

 delete : deletes the "paper" ColDoc from the site;
 isthere : checks that there is a "paper".
"""

############## system modules

import os, sys, argparse, functools
import os.path
from os.path import join as osjoin


if __name__ == '__main__':
    for j in ('','.'):
        while j in sys.path:
            sys.stderr.write('Warning: deleting %r from sys.path\n',j)
            del sys.path[sys.path.index(j)]
    #
    a = os.path.realpath(sys.argv[0])
    a = os.path.dirname(a)
    a = os.path.dirname(a)
    COLDOC_SRC_ROOT=a
    os.environ['COLDOC_SRC_ROOT'] = COLDOC_SRC_ROOT
    a = osjoin(a, 'ColDocDjango')
    assert os.path.isdir(a), a
    if a not in sys.path:
        sys.path.insert(0, a)
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)

def main(argv):
    COLDOC_SITE_ROOT =  osjoin(COLDOC_SRC_ROOT,'test','tmp','test_site')
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT',COLDOC_SITE_ROOT)
    if not os.path.isdir(COLDOC_SITE_ROOT):
        COLDOC_SITE_ROOT = None
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', help='specific command')
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('--blobs-dir',type=str,\
                        help='directory where the blob_ized output is saved')
    parser.add_argument('--coldoc-nick',type=str, required=True,\
                        help='nickname for the coldoc document', default='paper')
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    args = parser.parse_args(argv)
    COLDOC_SITE_ROOT = args.coldoc_site_root
    assert os.path.isdir(COLDOC_SITE_ROOT), COLDOC_SITE_ROOT
    os.environ['COLDOC_SITE_ROOT'] = COLDOC_SITE_ROOT
    #
    a = osjoin(COLDOC_SITE_ROOT,'coldocs',args.coldoc_nick,'blobs')
    if args.blobs_dir is None:
        args.blobs_dir = a
    else:
        assert os.path.isdir(args.blobs_dir) , args.blobs_dir
    if args.blobs_dir != a:
        logger.warning('mismatch --blobs-dir = %r is not the expected %r', args.blobs_dir , a)
    #
    options = {}
    #
    #os.environ.setdefault('DJANGO_SETTINGS_MODULE', osjoin(COLDOC_SRC_ROOT,'ColDocDjango','settings.py'))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ColDocDjango.settings'
    import django
    django.setup()
    import ColDocApp.models as coldocapp_models
    import UUID.models as  blob_models
    #
    matches = list(coldocapp_models.DColDoc.objects.filter(nickname = args.coldoc_nick))
    if len(matches) > 1 :
        raise ValueError("Too many ColDoc with nick %r." % (args.coldoc_nick,) )
    #
    #
    if args.command == 'isthere':
        print('yes' if len(matches) == 1 else 'no')
        return (0 if len(matches) == 1 else 13)
    if args.command == 'delete':
        if len(matches) == 0 :
            raise ValueError("No such ColDoc %r." % (args.coldoc_nick,) )
        coldoc = matches[0]
        print('Deleting %r'%(coldoc,))
        coldoc.delete()
        return (0)
    else:
        print(__doc__)
        return (1)


if __name__ == '__main__':
    sys.exit( main(sys.argv[1:]) )
