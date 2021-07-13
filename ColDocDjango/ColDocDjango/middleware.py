from django.utils.deprecation import MiddlewareMixin

##  https://stackoverflow.com/a/9362519/5058564
class RemoteUserMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.user.is_authenticated:
            response['X-Remote-User-Name'] = request.user.username
            response['X-Remote-User-Id'] = request.user.id
        return response
