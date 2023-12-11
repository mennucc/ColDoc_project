# example of initialization code, that may be put in init.py in the instance

from django.core.mail import mail_admins
from django.utils.html import escape

import logging
logger = logging.getLogger(__name__)

# specify a group to add users to when they login in or sign in
groupname = None
# but only if their email is validated and is in a specific domain
emaildomain = '@domain.net'
# and on first addition, donate some coins
coins = 600

def user_blah_callback(text, sender, **kwargs):
    try:
        # collect info to send email
        user    = kwargs.get('user')  # ColDocUser instance
        signal  = kwargs.get('signal')  #django.dispatch.dispatcher.Signal instance
        request = kwargs.get('request') # WSGIRequest instance
        response = kwargs.get('response') # HttpResponseRedirect or similar\
        sociallogin = kwargs.get('sociallogin') # allauth.socialaccount.models.SocialLogin object
        #
        url = user.get_absolute_url()
        adminurl = '/admin/ColDocApp/coldocuser/%d/change/' % (user.id, )
        url = request.build_absolute_uri(url)
        adminurl = request.build_absolute_uri(adminurl)
        subject = 'user %s : %s ' % (  user, text)
        su = str(user)
        tm = ' user %s : %s ; %s  \n admin %s' % (su, text, url, adminurl)
        hm = '<a href="%s">user %s</a> : %s <br>\n <a href="%s"> admin </a> <br>\n' %\
            ( url, escape(su), text, adminurl)
        #
        from ColDocDjango.utils import get_email_for_user
        if  user :
            email = get_email_for_user(user)
            tm += '\n email=' + repr(email)
            hm += '<br>  email=' + repr(email)
        if user and groupname:
            # maybe add user to group
            if user.groups.filter(name = groupname).exists():
                tm += '\n already in group ' + groupname
                hm += '<br> already in group ' + groupname
            elif email and (not emaildomain or email.endswith(emaildomain)):
                # add user to group
                from django.contrib.auth.models import Group
                my_group = Group.objects.get(name=groupname)
                my_group.user_set.add(user)
                tm += '\n added to group ' + groupname
                hm += '<br> added to group ' + groupname
                from django.conf import settings
                # donate coins
                if coins and settings.USE_WALLET:
                    import wallet, wallet.utils
                    s = ('giving %d coins ' % (coins, ))
                    tm += '\n' + s
                    hm += '<br>' + s
                    wallet.utils.deposit(coins, user)
        logger.info(tm)
        mail_admins(subject = subject, message = tm, html_message=hm)
    except:
        logger.exception('failure')

# attach the above code to the allauth signals

def user_signed_up_callback(sender, **kwargs):
    return user_blah_callback('signed up', sender, **kwargs)

def user_logged_in_callback(sender, **kwargs):
    return user_blah_callback('logged in', sender, **kwargs)

from allauth.account.signals import user_signed_up, user_logged_in
user_signed_up.connect(user_signed_up_callback)
user_logged_in.connect(user_logged_in_callback)

# send email to admins

s = 'coldoc started'
mail_admins(subject = s, message = s, html_message=s)


