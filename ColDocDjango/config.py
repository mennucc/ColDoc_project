#!/usr/bin/env python3
__all__ = ('config', 'CONFIG_FILENAMES', 'deploy')

import os, sys

import logging
logger = logging.getLogger(__name__)

import configparser


config = configparser.ConfigParser()

BASE_ROOT = os.path.dirname(os.path.abspath(__file__))
section = 'DEFAULT'
config.set(section, 'base_root', BASE_ROOT)
config.set(section, 'virtualenv', '')
config.set(section, 'site_name', 'ColDoc Test Site')

section = 'django'
config.add_section(section)
config.set(section, 'debug', 'True')
config.set(section, 'secret_key', '')
config.set(section, 'hostname', 'localhost')
config.set(section, 'server_url', 'http://localhost')
config.set(section, 'allowed_hosts', '127.0.0.1,localhost')
config.set(section, 'root_url', '/')
config.set(section, 'static_root', '%(base_root)s/static_collect')
config.set(section, 'static_dir', '%(base_root)s/static')
config.set(section, 'static_url', '/static/')
config.set(section, 'media_root', '%(base_root)s/media')
config.set(section, 'media_url', '/media/')
config.set(section, 'template_dirs', '%(base_root)s/templates')
config.set(section, 'sqlite_database', '%(base_root)s/var/db.sqlite3')


section = 'web'
config.add_section(section)
config.set(section, 'google_site_verification', '')
config.set(section, 'google_analytics_account', '')
config.set(section, 'piwik_url', '')
config.set(section, 'piwik_site_id', '')


def deploy(con, a):
    " write configuration `con` to file `a` to allow for customization"
    from pathlib import Path
    # get_random_secret_key() would often create a string that cannot be interpolated
    from django.core.management.utils import get_random_string
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    con.set('django', 'secret_key', get_random_string(50, chars))
    #
    con._interpolation = configparser.Interpolation()
    con.set('DEFAULT', 'user_home', os.path.expanduser('~'))
    con.set('django', 'debug', 'False')
    con['DEFAULT'].pop('base_root')
    if isinstance(a,(str, Path)):
        a = open(a,'w')
    a.write('# `base_root` will be automatically set to the directory\n# where this file is located, to ease relocation\n')
    con.write(a)

def integrate(inifile,config):
    "read `inifile` into `config`, change base_root"
    config.read([inifile])
    config.set('DEFAULT', 'base_root', os.path.dirname(os.path.abspath(inifile)))


if __name__ == '__main__':
    #a = os.path.realpath(sys.argv[0])
    #a = os.path.dirname(a)
    #a = os.path.dirname(a)
    #assert os.path.isdir(a), a
    #if a not in sys.path:
    #    sys.path.insert(0, a)
    #del a
    #
    #from ColDoc import ColDocLogging
    import sys
    if len(sys.argv) in (2,3) and sys.argv[1] == 'inspect':
        if len(sys.argv) == 3:
            integrate(sys.argv[2],config)
        config.write(sys.stdout)
        raise SystemExit(0)
    elif len(sys.argv) == 3 and sys.argv[1] == 'deploy':
        a = sys.argv[2]
        if os.path.exists(a) or os.path.islink(a):
            sys.stderr.write("Won't overwrite: %r\n"%(a,))
            raise SystemExit(2)
        deploy(config, a)
        raise SystemExit(0)
    elif len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ('help','-h','--help')):
        sys.stderr.write("""Usage: %r [commands]

Commands:

  deploy FILENAME
    create a copy of the standard config in FILENAME, that may be customized,
    if FILENAME is `config.ini` in the current directory

  inspect [FILENAME]
    return the standard config, or the config provided by the init file FILENAME,
    as django will see it
"""%(sys.argv[0],))
        raise SystemExit(0)
    else:
        sys.stderr.write('Unimplemented command %r\nTry --help\n'%(sys.argv,))
        raise SystemExit(1)

else:
    CONFIG_FILENAMES = []
    if 'COLDOC_SITE_ROOT' in os.environ:
        CONFIG_FILENAMES.append(os.path.join(os.environ['COLDOC_SITE_ROOT'],'config.ini'))

    CONFIG_FILENAMES.append(os.path.join(BASE_ROOT, 'config.ini'))

    #"search for an ini file and add it"
    for conf in CONFIG_FILENAMES:
        if os.path.exists(conf):
            logger.info("Reading config file: %r", conf)
            integrate(conf,config)
            break
    else:
        logger.warning("Cannot find config file. Tried: %r" ,
                       ', '.join(CONFIG_FILENAMES))

