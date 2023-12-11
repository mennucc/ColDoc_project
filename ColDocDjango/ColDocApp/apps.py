import logging, os
from os.path import join as osjoin

logger = logging.getLogger(__name__)

from django.apps import AppConfig

def remove_locks():
    from django.conf import settings
    try:
        d = osjoin(settings.COLDOC_SITE_ROOT, 'lock')
        if not os.path.isdir(d):
            return
        # FIXME should remove also the other files
        for j in os.listdir(d):
            if j.endswith('.lock'):
                try:
                    os.unlink(osjoin(d,j))
                except OSError:
                    logger.warning("Cannot remove lock %r ", j)
                else:
                    logger.info("Removed lock %r ", j)
    except:
        logger.exception("While cleaning locks")

def run_init_code():
    from django.conf import settings
    try:
        init = osjoin(settings.COLDOC_SITE_ROOT, 'init.py')
        if not os.path.isfile(init):
            return
        exec(compile(open(init).read(),init,'exec'))
    except:
        logger.exception("While running site init code from %r", init)


class ColdocappConfig(AppConfig):
    name = 'ColDocApp'
    default_auto_field = 'django.db.models.AutoField'
    def ready(self):
        remove_locks()
        run_init_code()
