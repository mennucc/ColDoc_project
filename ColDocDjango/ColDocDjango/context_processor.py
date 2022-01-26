# https://stackoverflow.com/a/433209

from django.conf import settings # import the settings file

def add_settings(request):
    # return the value you want as a dictionnary. you may add multiple values in there.
    return {'USE_ALLAUTH': settings.USE_ALLAUTH,
            'USE_BACKGROUND_TASKS': settings.USE_BACKGROUND_TASKS,
            'USE_WALLET': settings.USE_WALLET,
            'USE_CODEMIRROR': settings.USE_CODEMIRROR,
            'GOOGLE_ANALYTICS4' : settings.GOOGLE_ANALYTICS4,
            }
