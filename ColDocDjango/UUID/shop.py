import os, sys, mimetypes, http, copy, json, hashlib, base64, pickle

import logging
logger = logging.getLogger(__name__)

import django

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
        D = { 'return_code' : True,
              'related_object' : related_object,
        }
        return D
    #
    def __call__(self, *v,**k):
        return self.buy(*v,**k)


def buy_download(request, obj, NICK, UUID):
    from django_pursed.wallet.utils import encode_purchase
    purchase_amount = '20'
    description = "buy the download of coldoc=%r uuid=%r" % (NICK,UUID)
    x = BuyPermission('download',request.user,obj)
    pickled_function = base64.b64encode(pickle.dumps(x)).decode()
    redirect_ok =  request.get_full_path()
    redirect_fails =  django.urls.reverse('UUID:index', kwargs={'NICK':NICK,'UUID':UUID}) 
    encoded = encode_purchase(purchase_amount, description, pickled_function, redirect_ok, redirect_fails)
    return django.shortcuts.redirect(django.urls.reverse('wallet:authorize_purchase_url', kwargs={'encoded' : encoded}))

