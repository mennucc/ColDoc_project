import os, sys, mimetypes, http, copy, json, hashlib, base64, pickle

import logging
logger = logging.getLogger(__name__)

import django
from django.contrib import messages
from django.conf import settings

try:
    import guardian
except ImportError:
    guardian = None
    UserObjectPermission = None
else:
    from guardian.models import UserObjectPermission

try:
    import django_pursed
except ImportError:
    django_pursed = None
    StopPurchase = Exception
else:
    from django_pursed.wallet.errors import StopPurchase

class BuyPermission(object):
    def __init__(self, perm, user, obj):
        self.user = user
        self.obj = obj
        self.perm = perm
    #
    def check(self, *v,**k):
        perm = self.perm
        if self.user.has_perm(perm, self.obj):
            raise StopPurchase( 'User %r already owns permission %r' % (self.user, self.perm, ) )
        if UserObjectPermission is None:
            raise StopPurchase( 'Internal Error, django-guardian unavailable')
    #
    def buy(self, *v,**k):
        self.check()
        related_object = UserObjectPermission.objects.assign_perm(perm=self.perm, user_or_group=self.user, obj=self.obj)
        logger.info('User %r bought permission %r for blob %r', self.user, self.perm, self.obj)
        D = { 'return_code' : True,
              'related_object' : related_object,
        }
        return D
    #
    def __call__(self, *v,**k):
        return self.buy(*v,**k)


def can_buy_permission(user, blob, permission ):
    " returns a `str`  explain why the user cannot but the permission, otherwise a `float` the cost of the purchase"
    #
    if not settings.USE_WALLET:
        return 'settings.USE_WALLET is False'
    #
    if UserObjectPermission is None:
        return  'Internal Error, django-guardian unavailable'
    #
    if not user.has_perm('wallet.operate'):
        return 'User %r cannot operate on wallets' % (user,)
    #
    try:
        return settings.PRICE_FOR_PERMISSION(user, blob, permission )
    except Exception as e:
        logger.exception('While computing price: ')
        return '[Internal error when computing price]'


def buy_permission(user, blob, permission, amount, request=None, redirect_ok = None, redirect_fails = None, ):
    "returns the URL to but this permission"
    NICK = blob.coldoc.nickname
    UUID = blob.uuid
    if redirect_fails is None:
        redirect_fails =  django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) 
    if redirect_ok is None:
        if request:
            redirect_ok =  request.get_full_path()
        else:
            redirect_ok = redirect_fails
    #
    assert django_pursed is not None
    from django_pursed.wallet.utils import encode_purchase, encode_buying_function
    description = "buy the permission %r for uuid=%r coldoc=%r" % (permission, UUID, NICK)
    x = BuyPermission(permission, user, blob)
    #
    try:
        x.check()
    except StopPurchase as e:
        a = 'Purchase stopped : %s' % (e,)
        logger.warning(a)
        messages.add_message(request,messages.WARNING, a)
        return False
    except Exception as e:
        a = 'Purchase check failed : %r' % (e,)
        messages.add_message(request,messages.ERROR, a)
        logger.error(a)
        return False
    #
    pickled_function = encode_buying_function(x)
    encoded = encode_purchase(amount, description, pickled_function, redirect_ok, redirect_fails)
    return django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded})


