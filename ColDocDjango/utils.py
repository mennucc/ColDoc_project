import os, sys, mimetypes, http, json
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

import django


def convert_latex_return_codes(latex_return_codes, NICK, UUID):
    latex_error_logs = []
    try:
        d = latex_return_codes
        if  d:
            d = json.loads(d)
            for k,v in d.items():
                if not v:
                    if ':' in k:
                        e,l = k.split(':')
                    else:
                        e,l = k,''
                    e_ = {'latex':'.log', 'plastex':'_plastex.log'}[e]
                    a = django.urls.reverse( 'UUID:log',   kwargs={'NICK':NICK,'UUID':UUID})
                    if a[-1] != '/': a += '/'
                    a += '?lang=%s&ext=%s'  % (l,e_)
                    latex_error_logs.append(  (e, a ) )
    except:
        logger.exception("While reading latex_return_codes")
    return latex_error_logs
