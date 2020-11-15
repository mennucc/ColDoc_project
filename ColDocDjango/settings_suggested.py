### these are some settings that are suggested 

MAIL_HOST = "smtp.server"
EMAIL_PORT = "587"
EMAIL_HOST_USER = "username"
EMAIL_HOST_PASSWORD = "password"
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "Helpdesk <helpdesk@that_email>"


## as per https://bugs.freedesktop.org/show_bug.cgi?id=5455

import mimetypes
for j in ('.gplt','.gnuplot'):
    mimetypes.add_type('application/x-gnuplot',j)

## Google analytics

GOOGLE_SITE_VERIFICATION = 'googleXXXXXXXXXXXXXXXX.html'

# you can add analytics by copying the template `analytics.html` in your deployed site and editing it
# a template for Google analytics 4 can be activated by entering the G-code below

GOOGLE_ANALYTICS4 = 'G-xxxxxxxxxx'


