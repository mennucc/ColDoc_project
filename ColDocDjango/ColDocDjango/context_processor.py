# https://stackoverflow.com/a/433209

import time

from django.conf import settings # import the settings file

def add_settings(request):
    # return the value you want as a dictionnary. you may add multiple values in there.
    if not request.user.is_anonymous:
        session_expiry_age = request.session.get_expiry_age()
        session_expiry_time = session_expiry_age + int(time.time())
    else:
        session_expiry_age = -1
        session_expiry_time = -1
    return {'USE_ALLAUTH': settings.USE_ALLAUTH,
            'USE_BACKGROUND_TASKS': settings.USE_BACKGROUND_TASKS,
            'USE_WALLET': settings.USE_WALLET,
            'USE_CODEMIRROR': settings.USE_CODEMIRROR,
            'GOOGLE_ANALYTICS4' : settings.GOOGLE_ANALYTICS4,
            'session_expiry_age' : session_expiry_age,
            'session_expiry_time': session_expiry_time,
            }
