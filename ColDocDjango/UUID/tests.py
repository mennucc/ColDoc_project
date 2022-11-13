import tempfile, os, io
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


import logging
logger = logging.getLogger(__name__)

User = get_user_model()

show_in_firefox = False

class ColDocTestCase(TransactionTestCase):
    #
    def setUp(self):
        logger.info('Creating users...')
        import helper
        helper.create_fake_users(log=lambda x:x)
        logger.info('Users created.')


class permissions(ColDocTestCase):
    #
    def _test_wallet(self, username='jsmith', password='123456', can=False, firefox=False):
        #
        import django
        from django.conf import settings
        # https://docs.djangoproject.com/en/4.1/topics/testing/tools/
        c = Client()
        if True:
            r1 = c.post('/login/', {'username': username, 'password': password})
            #print('response=%r url=%r'  %  (r1.status_code, r1.url))
        else:
            c.login(username, password)
        #self.assertRedirects(r)
        #print(c.cookies)
        ##
        r2 = c.get(r1.url)
        if firefox:
            t2 = tempfile.NamedTemporaryFile(delete=False,suffix='.html')
            open(t2.name,'w').write(r2.content.decode())
            os.system('firefox %s &' % (t2.name,))
        ##
        if settings.USE_WALLET:
            r3 = c.get('/wallet/show')
            #print('response=%r' % r3.status_code)
            if can:
                self.assertEqual(r3.status_code , 200)
            else:
                self.assertEqual(r3.status_code , 400)
            if firefox:
                t3 = tempfile.NamedTemporaryFile(delete=False,suffix='.html')
                open(t3.name,'w').write(r3.content.decode())
                os.system('firefox %s &' % (t3.name,))
    #
    def test_wallet1(self):
        return self._test_wallet('jsmith', '123456', False, firefox= show_in_firefox)
    #
    def test_wallet2(self):
        return self._test_wallet('buyer', 'barfoo', True, firefox= show_in_firefox)

