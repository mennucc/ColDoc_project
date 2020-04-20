#!/usr/bin/env python3

""" the Blob Inator
splits the input into blobs

(this version is integrated with Django)
"""

############## system modules

import os, sys, argparse, functools
import os.path
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
    COLDOC_SRC_ROOT=a
    del a
    #
    from ColDoc import loggin

import logging
logger = logging.getLogger(__name__)


############# django

import django

from django.db import transaction

from django.core.validators  import validate_slug

############## ColDoc stuff

import ColDoc.blob_inator as BI


if __name__ == '__main__':
    BI.COLDOC_SRC_ROOT = COLDOC_SRC_ROOT
    #
    parser = argparse.ArgumentParser(description='Splits a TeX or LaTeX input into blobs',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--coldoc-nick',type=str,\
                        help='nickname for the new coldoc document',\
                        required=True)
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='directory where the ColDoc Django site was deployed')
    BI.add_arguments_to_parser(parser)
    args = parser.parse_args()
    #
    if args.coldoc_site_root is not None:
        COLDOC_SITE_ROOT = args.coldoc_site_root
    elif  'COLDOC_SITE_ROOT' in os.environ:
        COLDOC_SITE_ROOT = args.coldoc_site_root = os.environ['COLDOC_SITE_ROOT']
    else:
        COLDOC_SITE_ROOT = None #os.path.dirname(os.path.abspath(__file__))
    #
    if COLDOC_SITE_ROOT is None or not os.path.isfile(os.path.join(COLDOC_SITE_ROOT,'config.ini')):
        if COLDOC_SITE_ROOT is not None:
            sys.stderr.write("""\
The directory
COLDOC_SITE_ROOT={COLDOC_SITE_ROOT}
does not contain the file `config.ini`
""".format_map(locals()) )
        sys.stderr.write("""
Please use the option `--coldoc-site-root` or the environment  variable COLDOC_SITE_ROOT
to specify where the ColDoc site is located.
""" )
        sys.exit(1)
    #
    os.environ.setdefault('COLDOC_SITE_ROOT', COLDOC_SITE_ROOT)
    #
    j = os.path.join(COLDOC_SITE_ROOT,'settings')
    if os.path.exists(j+'.py'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', j)
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    #
    django.setup()
    import ColDocDjango.ColDocApp.models as coldocapp_models
    import ColDocDjango.UUID.models as  blob_models
    #
    ## check that usernames are ColDocUser
    from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
    for j in args.author:
        try:
            a = coldocapp_models.ColDocUser.objects.get(username=j)
        except ObjectDoesNotExist:
            sys.stderr.write('No user %r in Django database\n'%(j,))
            sys.exit(1)
    #
    try:
        #validate_slug.message =
        validate_slug(args.coldoc_nick)
    except Exception as e:
        sys.stderr.write('Invalid coldoc_nick=%r\n'%(args.coldoc_nick,))
        sys.exit(1)
    if args.coldoc_nick in ('static','static_collect','static_root','static_local','media',
                            'usr','var','lib','etc','src','pdf','html',
                            'jpeg','jpg','tiff','tif'):
        sys.stderr.write('Cannot use coldoc_nick=%r\n'%(args.coldoc_nick,))
        sys.exit(1)
    #
    coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',args.coldoc_nick)
    if os.path.exists(coldoc_dir):
        sys.stderr.write('Warning, already exists coldoc_dir=%r\n'%(coldoc_dir))
    else:
        os.mkdir(coldoc_dir)
    #
    args_json = osjoin(coldoc_dir, 'blob_inator-args.json')
    if os.path.exists(args_json):
        sys.stderr.write("Will not overwrite: %r\n"%(args_json,))
        sys.exit(1)
    #
    args.blobs_dir = blobs_dir = osjoin(coldoc_dir, 'blobs')
    #
    for j in 'git', 'anon', 'users', 'blobs':
        j = osjoin(coldoc_dir,j)
        if not os.path.exists(j):
            os.mkdir(j)
        else:
            assert os.path.isdir(j), 'Not a dir: %r'%(j,)
    # https://docs.djangoproject.com/en/3.0/topics/db/transactions/
    with transaction.atomic():
        c = list(coldocapp_models.DColDoc.objects.filter(nickname = args.coldoc_nick))
        if not c:
            coldoc = coldocapp_models.DColDoc()
            coldoc.nickname = args.coldoc_nick
        else:
            coldoc = c[0]
            logger.warning('Reusing nick %r',args.coldoc_nick)
        coldoc.directory = coldoc_dir
        coldoc.save()
        r =  BI.main(args, metadata_class=blob_models.DMetadata, coldoc=coldoc)
        coldoc.save()
    #
    import ColDocDjango.utils as CDutils
    with transaction.atomic():
        CDutils.add_permissions_for_coldoc(coldoc.nickname)
    #
    sys.exit(r)
