import datetime
from functools import wraps
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render
from ColDocDjango import settings

from ColDocDjango.ColDocApp.models import DColDoc

def catcher(view_func):
    """
    Decorator that catches some exceptions:
    Redirect: redirect to given URL
    """
    def wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except InvalidRequest:
            add_message(request, ERROR, 'Invalid request')
            return HttpResponseRedirect(ROOT_URL)
        except NotAuthorized:
            add_message(request, ERROR, 'Not Authorized')
            return HttpResponseRedirect(ROOT_URL)
        except Redirect as e:
            return HttpResponseRedirect(e.url)
        except NotFound:
            c = default_context_for(request)
            c['root_url'] = ROOT_URL
            return HttpResponseNotFound(render_to_string('404.html', c))
#        except ArxivError as e:
#            log(request.user, "arxiv error", ['{}'.format(e)])
#            add_message(request, ERROR, 'Arxiv error: {}'.format(e))
#            return HttpResponseRedirect(request.path)
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)



#@catcher
def main_page(request):
    c = {'DColDocs':DColDoc.objects.all()} #default_context_for(request)
    now = datetime.date.today()
    user = request.user
    return render(request, 'index.html', c)

