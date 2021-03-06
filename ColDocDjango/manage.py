#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os, copy, sys


def main():
    argv = copy.copy(sys.argv)
    #
    COLDOC_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, COLDOC_DIR)
    #
    if '--coldoc-site-root' in argv:
        j = argv.index('--coldoc-site-root')
        COLDOC_SITE_ROOT = argv.pop(1+j)
        argv.pop(j)
        os.environ.setdefault('COLDOC_SITE_ROOT', COLDOC_SITE_ROOT)
    elif  'COLDOC_SITE_ROOT' in os.environ:
        COLDOC_SITE_ROOT = os.environ['COLDOC_SITE_ROOT']
    else:
        COLDOC_SITE_ROOT = None #os.path.dirname(os.path.abspath(__file__))
    #
    if (len(argv)>1 and argv[1] not in ('help','startapp')) and \
          (COLDOC_SITE_ROOT is None or \
           not os.path.isfile(os.path.join(COLDOC_SITE_ROOT,'config.ini'))):
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
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    #
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(argv)


if __name__ == '__main__':
    import logging
    from logging import Logger, StreamHandler, Formatter
    logger = logging.getLogger(__name__)
    handler = StreamHandler(sys.stderr)
    #LOG_FORMAT = '[%(name)s - %(funcName)s - %(levelname)s] %(message)s'
    #handler.setFormatter(Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    #
    for j in ('','.'):
        if j in sys.path:
            logger.warning('del %r from sys.path',j)
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
    if 'COLDOC_SRC_ROOT' in os.environ and COLDOC_SRC_ROOT != os.environ['COLDOC_SRC_ROOT']:
        logger.error('Substituting environment COLDOC_SRC_ROOT=% with %r',os.environ('COLDOC_SRC_ROOT'))
    os.environ['COLDOC_SRC_ROOT'] = COLDOC_SRC_ROOT
    #
    #
    main()
