### these are some settings that are suggested 

MAIL_HOST = "smtp.server"
EMAIL_PORT = "587"
EMAIL_HOST_USER = "username"
EMAIL_HOST_PASSWORD = "password"
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "helpdesk@that_email"


## as per https://bugs.freedesktop.org/show_bug.cgi?id=5455

import mimetypes
for j in ('.gplt','.gnuplot'):
    mimetypes.add_type('application/x-gnuplot',j)

## Google analytics

GOOGLE_SITE_VERIFICATION = 'googleXXXXXXXXXXXXXXXX.html'

# you can add analytics by copying the template `analytics.html` in your deployed site and editing it
# a template for Google analytics 4 can be activated by entering the G-code below

GOOGLE_ANALYTICS4 = 'G-xxxxxxxxxx'


###############
## example of pricing function, that may be used with `paper` coldoc , as generated by `make -C test django_paper`

def PRICE_FOR_PERMISSION(user, blob, permission ):
    " returns a `str`  explain why the user cannot but the permission, otherwise a `float` or `int`, the cost of the purchase"
    envs = blob.get('environ')
    env = envs[0] if envs else ''
    print(permission)
    if permission == 'download' and user.has_perm('UUID.view_view') and ('preamble' not in env):
        # in this example, an user with `operate` on wallet can by `download` of anything that is not `preamble`
        return 20
    elif env in  ('E_buyablecontent') and permission == 'view_view':
        return 100
    else:
        return 'User %r cannot buy permission %r for blob %r' % (user, permission, blob)
