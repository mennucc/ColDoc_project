from django.middleware.locale import LocaleMiddleware as dLM
from django.utils import translation
from django.conf import settings


import logging
logger = logging.getLogger(__name__)


try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object

##  https://stackoverflow.com/a/9362519/5058564
class RemoteUserMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.user.is_authenticated:
            response['X-Remote-User-Name'] = request.user.username
            response['X-Remote-User-Id'] = request.user.id
        return response

# https://stackoverflow.com/a/13677273/5058564

from django import shortcuts

class RedirectException(Exception):
    def __init__(self, url, permanent=False):
        self.url = url
        self.permanent = permanent

def redirect_by_exception(url, permanent=False):
    raise RedirectException(url, permanent)

class RedirectMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, RedirectException):
            return shortcuts.redirect(exception.url, exception.permanent)


###############


class LocaleMiddleware(dLM):
    """ wrapper for django locale middleware, to cover bots and `lang=` """

    def process_request(self, request):
        """ search engine bots do not use  HTTP_ACCEPT_LANGUAGE """
        accept = request.META.get("HTTP_ACCEPT_LANGUAGE")
        cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if accept is None and cookie is None:
            # import here to avoid circular dependency
            from ColDocDjango.utils import iso3lang2iso2
            from ColDoc.utils import lang_re
            #
            lang = request.GET.get('lang')
            if lang and lang_re.match(lang):
                lang2 = iso3lang2iso2(lang)
                if lang2:
                    translation.activate(lang2)
                    request.LANGUAGE_CODE = translation.get_language()
                    logger.debug('bot request %r (?) setting lang to %r -> %r',
                                 request.META.get("HTTP_USER_AGENT"), lang, request.LANGUAGE_CODE)
                    return
        return super().process_request(request)

