#!/usr/bin/env python3


"""Usage: %(arg0)s [-v] --coldoc_site_root COLDOC_SITE_ROOT  CMD [OPTIONS]

Administration of a ColDoc site

This program does some actions that `manage` does not.

    deploy
        create a new ColDoc site
"""

import os, sys, argparse
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



def deploy(target):
    from ColDocDjango import config
    if os.path.exists(target):
        if not os.path.isdir(target):
            sys.stderr.write('exists and not dir: %r\n' % target)
            return False
        elif os.listdir(target):
            sys.stderr.write('exists and not empty: %r\n' % target)
            return False
    else:
        os.mkdir(target)
    #
    a = osjoin(target,'config.ini')
    if os.path.exists(a) or os.path.islink(a):
        sys.stderr.write("Won't overwrite: %r\n"%(a,))
        return False
    config.deploy(a)
    #
    newconfig = config.get_config(target)
    for j in ( 'coldocs' , ):
        os.mkdir(osjoin(target,j))
    # create 'media', , 'static_local', 'static_root':
    for j in 'media_root', 'template_dirs', 'static_root', 'static_local':
        a = newconfig['django'][j]
        os.makedirs(a)
    a = newconfig.get('django','sqlite_database')
    if a is not None:
        a = os.path.dirname(a)
        if not os.path.isdir(a):
            os.makedirs(a)
    return True


def main(argv):
    parser = argparse.ArgumentParser(description='deploy a ColDoc site',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
    parser.add_argument('--coldoc-site-root',type=str,\
                        help='root of the coldoc portal (default from env `COLDOC_SITE_ROOT`)', default=COLDOC_SITE_ROOT,
                        required=(COLDOC_SITE_ROOT is None))
    parser.add_argument('--verbose','-v',action='count',default=0)
    parser.add_argument('command', help='specific command',nargs='+')
    args = parser.parse_args()
    argv = args.command
    #
    COLDOC_SITE_ROOT = os.environ['COLDOC_SITE_ROOT'] = args.coldoc_site_root
    if argv[0] == 'deploy':
        return deploy(COLDOC_SITE_ROOT)
    else:
        sys.stderr.write("command not recognized : %r\n",argv)
        sys.stderr.write(__doc__%{'arg0':sys.argv[0]})
        return False
    return True

if __name__ == '__main__':
    ret = main(sys.argv)
    sys.exit(0 if ret else 13)

