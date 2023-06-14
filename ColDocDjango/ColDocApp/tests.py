import os,sys

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import helper

def client_login(username,password):
    " returns logged in client"
    User = get_user_model()
    u = User.objects.filter(username=username).all()
    if not u:
        logger.error('User %r does not exist in db',username)
    if not username in helper.fake_users:
        logger.error('User %r is not one of fake users',username)
    c = Client()
    logger.info('login %r', username)
    # get csfrtoken
    r0 = c.get('/')
    #print(r0.status_code, c.cookies)
    # try simple direct mode
    c.login(username=username, password=password)
    if 'sessionid' in c.cookies.keys():
        return c
    # try post
    r0 = c.get('/login/?next=/')
    #print(r0.status_code, c.cookies)
    #
    r0 = c.post('/login/', {'username': username, 'password': password, 'next':'/' } )
    #print(r0.status_code, c.cookies)
    #_firefox_show(r1.content)
    #
    #print(r0.status_code,c.cookies)
    return c

class ColDocTestCase(TransactionTestCase):
    # fixme this would be faster
    #fixtures = ['test_users.json.xz']
    #
    def setUp(self):
        COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')
        helper.create_fake_users(COLDOC_SITE_ROOT, lambda x:x)

class General(ColDocTestCase):
    def test_login_page(self):
        User = get_user_model()
        allusers = User.objects.all()
        if len(allusers) <= 1:
            logger.error('Internal problem, fake users are not in the database', allusers)
        #
        username='jsmith'
        password='123456'
        #
        c = client_login(username,password)
        r0 = c.get('/')
        #_firefox_show(r0.content)
        self.assertEqual(r0.status_code , 200)
        self.assertContains(r0, "Succesfully logged in")

    def test_nologin_page(self):
        User = get_user_model()
        #
        allusers = User.objects.all()
        if len(allusers) <= 1:
            logger.error('Internal problem, fake users are not in the database', allusers)
        #
        username='jsmith'
        password='wrong'
        #
        c = client_login(username,password)
        r0 = c.get('/')
        #print(r0.status_code, c.cookies)
        #_firefox_show(r0.content)
        self.assertEqual(r0.status_code , 200)
        self.assertContains(r0,"😑")
