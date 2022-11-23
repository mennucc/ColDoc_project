
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
    def __init__(self, url):
        self.url = url

def redirect_by_exception(url):
    raise RedirectException(url)

class RedirectMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, RedirectException):
            return shortcuts.redirect(exception.url)
