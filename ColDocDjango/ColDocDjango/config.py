#!/usr/bin/env python3
__all__ = ('get_config', 'get_base_config', 'deploy')

import os, sys, copy

import logging
logger = logging.getLogger(__name__)

import configparser

config = configparser.ConfigParser()

BASE_ROOT = os.path.dirname(os.path.abspath(__file__))
section = 'DEFAULT'
config.set(section, 'site_root', os.path.join(BASE_ROOT,'fake_site_root'))
config.set(section, 'virtualenv', '')
config.set(section, 'site_name', 'ColDoc Test Site')

section = 'django'
config.add_section(section)
config.set(section, 'debug', 'True')
config.set(section, 'secret_key', '')
config.set(section, 'use_allauth', 'False')
config.set(section, 'use_background_tasks', 'True')
## this is not yet implemented
config.set(section, 'use_recaptcha', 'False')

config.set(section, 'use_simple_captcha', 'False')
config.set(section, 'use_wallet', 'False')
config.set(section, 'use_whitenoise', 'False')
config.set(section, 'hostname', 'localhost')
config.set(section, 'server_url', 'http://localhost')
config.set(section, 'allowed_hosts', '127.0.0.1,localhost')
config.set(section, 'root_url', '/')
config.set(section, 'static_root', '%(site_root)s/static_root')
config.set(section, 'static_local', '%(site_root)s/static_local')
config.set(section, 'static_url', '/static/')
config.set(section, 'dedup_root', '%(site_root)s/dedup')
config.set(section, 'dedup_url', '/dedup')
config.set(section, 'media_root', '%(site_root)s/media')
config.set(section, 'media_url', '/media/')
config.set(section, 'template_dirs', '%(site_root)s/templates')
config.set(section, 'sqlite_database', '%(site_root)s/var/db.sqlite3')


def deploy(a):
    " write configuration to file `a` to allow for customization"
    con = copy.copy(config)
    from pathlib import Path
    # get_random_secret_key() would often create a string that cannot be interpolated
    from django.core.management.utils import get_random_string
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    con.set('django', 'secret_key', get_random_string(50, chars))
    #
    con._interpolation = configparser.Interpolation()
    con.set('DEFAULT', 'user_home', os.path.expanduser('~'))
    con.set('django', 'debug', 'False')
    con['DEFAULT'].pop('site_root')
    if isinstance(a,(str, Path)):
        a = open(a,'w')
    a.write('# this config file is superimposed on %r\n'%(os.path.join(BASE_ROOT, 'config.ini')))
    a.write('# `site_root` will be automatically set to the directory\n# where this file is located, to ease relocation\n')
    con.write(a)

def integrate(inifile,config):
    "read `inifile` into `config`, change site_root"
    config.read([inifile])
    config.set('DEFAULT', 'site_root', os.path.dirname(os.path.abspath(inifile)))


if __name__ == '__main__':
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
        deploy(a)
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

def get_config(site_root = None):
    CONFIG_FILENAMES = []

    CONFIG_FILENAMES.append(os.path.join(BASE_ROOT, 'config.ini'))

    if site_root is None and 'COLDOC_SITE_ROOT' in os.environ:
        site_root = os.environ['COLDOC_SITE_ROOT']
    if site_root is None:
        logger.warning('no site_root for config.ini')
    else:
        CONFIG_FILENAMES.append(os.path.join(site_root,'config.ini'))

    config_ = copy.copy(config)
    #"search for an ini file and add it"
    for conf in CONFIG_FILENAMES:
        if os.path.exists(conf):
            logger.info("Reading config file: %r", conf)
            integrate(conf,config_)
            break
    else:
        logger.warning("Cannot find config file. Tried: %r" ,
                       ', '.join(CONFIG_FILENAMES))
    return config_

def get_base_config():
    return copy.copy(config)
