"""
Django settings for ColDoc project.

Generated by 'django-admin startproject' using Django 3.0.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/

** It is advisable not to edit this file to customize a deployed site **

If you want to customize this file for your specific coldoc site
instance, add your desired settings changes to 
'settings.py' file inside the COLDOC_SITE_ROOT directory.
That file will be executed after this file.
"""

import sys, os


import logging
logger = logging.getLogger(__name__)

from ColDocDjango.config import get_config

# do not customize this here, but in the `settings.py` file inside COLDOC_SITE_ROOT
SITE_ID = 1

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

COLDOC_SITE_CONFIG = config = get_config()

COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')

COLDOC_SRC_ROOT = os.environ.get('COLDOC_SRC_ROOT')

if COLDOC_SITE_ROOT is None:
    logger.error('COLDOC_SITE_ROOT is undefined')
elif not os.path.isfile(os.path.join(COLDOC_SITE_ROOT,'config.ini') ):
    logger.error('COLDOC_SITE_ROOT does not contain `config.ini`: %r ', COLDOC_SITE_ROOT)

if COLDOC_SRC_ROOT is None:
    COLDOC_SRC_ROOT = os.path.dirname(BASE_DIR)
    logger.error('COLDOC_SRC_ROOT is undefined, setting to %r',  COLDOC_SRC_ROOT)
elif not os.path.isfile(os.path.join(COLDOC_SRC_ROOT,'ColDocDjango','manage.py') ):
    logger.error('COLDOC_SRC_ROOT does not contain `ColDocDjango/manage.py`: %r ', COLDOC_SRC_ROOT)
else:
    a = os.path.join(COLDOC_SRC_ROOT,'ColDocDjango')
    if a not in sys.path:    
        sys.path.insert(0, a)

if COLDOC_SRC_ROOT != os.path.dirname(BASE_DIR):
    logger.warning('COLDOC_SRC_ROOT is %r, BASE_DIR parent is %r', COLDOC_SRC_ROOT, os.path.dirname(BASE_DIR))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config['django'].getboolean('debug')


AUTO_MUL = config['django'].getboolean('auto_mul')


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config.get('django','secret_key')
if not SECRET_KEY :
    if DEBUG:
        logger.warning('No secret_key in config files, using an insecure one')
        SECRET_KEY ='Aji_-Ofa9aV+d-Qmz_97VxxuZdaec1u5cucjpa2GMtm=Nu37sX'
    else:
        raise RuntimeError('No secret_key in config files')

ALLOWED_HOSTS = []
if config.get('django','allowed_hosts'):
    ALLOWED_HOSTS += config.get('django','allowed_hosts').split(',')

# django-allauth
# https://django-allauth.readthedocs.io/en/latest/installation.html#django
USE_ALLAUTH = config['django'].getboolean('use_allauth')

# https://django-background-tasks.readthedocs.io/en/latest/
USE_BACKGROUND_TASKS = config['django'].getboolean('use_background_tasks')
if USE_BACKGROUND_TASKS:
    try:
        import background_task
    except ImportError:
        logger.error('Please install `django-background-tasks`')
        USE_BACKGROUND_TASKS = False


USE_WALLET = config['django'].getboolean('use_wallet')

## This feature is not yet implemented
RECAPTCHA_PUBLIC_KEY = None
RECAPTCHA_PRIVATE_KEY = None
USE_RECAPTCHA = config['django'].getboolean('use_recaptcha')
if USE_RECAPTCHA:
    try:
        import django_recaptcha
    except ImportError:
        logger.error('Please install `django-recaptcha`')
        USE_RECAPTCHA = False
if USE_RECAPTCHA:
    logger.warning('recaptcha is not yet implemented')

##
USE_SIMPLE_CAPTCHA = config['django'].getboolean('use_simple_captcha')
if USE_SIMPLE_CAPTCHA:
    try:
        import captcha
    except ImportError:
        logger.error('Please install `django-simple-captcha`')
        USE_SIMPLE_CAPTCHA = False


# Application definition

INSTALLED_APPS = [
    'ColDocApp.apps.ColdocappConfig',
    'UUID.apps.UuidConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    #https://docs.djangoproject.com/en/3.0/howto/static-files/
    'django.contrib.staticfiles',
    'guardian',
]

if USE_ALLAUTH:
    INSTALLED_APPS += [
     'allauth',
     'allauth.account',
     'allauth.socialaccount', ]
## to add providers for your deployed site, add a snippet like this to the 
## settings.py file in COLDOC_SITE_ROOT
# INSTALLED_APPS += [
#     'allauth.socialaccount.providers.google']

if USE_BACKGROUND_TASKS:
    INSTALLED_APPS += ['background_task',]
    
if USE_RECAPTCHA or USE_SIMPLE_CAPTCHA:
    INSTALLED_APPS += ['captcha', ]

if USE_WALLET:
    INSTALLED_APPS += [ 'wallet', ]


AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]


LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

if USE_ALLAUTH:
    LOGIN_URL = '/accounts/login/'
    AUTHENTICATION_BACKENDS += [
        # `allauth` specific authentication methods, such as login by e-mail
        'allauth.account.auth_backends.AuthenticationBackend',
        ]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # https://github.com/bugov/django-custom-anonymous
    'ColDocDjango.custom_anonymous.AuthenticationMiddleware',
    'ColDocDjango.middleware.RemoteUserMiddleware',
    'ColDocDjango.middleware.RedirectMiddleware',
]

USE_SELECT2 = False
try:
    import django_select2
    INSTALLED_APPS.append('django_select2')
    USE_SELECT2 = True
except ImportError:
    logger.error('Please install `django-select2`')

# http://whitenoise.evans.io/en/stable/django.html
USE_WHITENOISE = config['django'].getboolean('use_whitenoise')
if USE_WHITENOISE:
    try:
        import whitenoise
    except ImportError:
        logger.warning('`whitenoise` not available, static files may be inaccessible')
    else:
        MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')
        STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        if DEBUG:
            logger.warning('`whitenoise` is disabled in debug mode')
        else:
            logger.info('`whitenoise` enabled')


ROOT_URLCONF = 'ColDocDjango.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ColDocDjango.context_processor.add_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'ColDocDjango.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': config.get('django','sqlite_database'),
    }
}

if not os.path.isfile(DATABASES['default']['NAME']):
    logger.warning('No database %r',DATABASES['default']['NAME'])

# https://docs.djangoproject.com/en/3.0/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project
AUTH_USER_MODEL = 'ColDocApp.ColDocUser'

# https://github.com/bugov/django-custom-anonymous
AUTH_ANONYMOUS_MODEL = 'ColDocDjango.users.ColDocAnonymousUser'

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

LOCALE_PATHS = [
    os.path.join(COLDOC_SRC_ROOT, 'ColDocDjango', 'locale'),
    ]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = config.get('django','static_url')

# use `manage.py collectstatic` to copy all files to this directory
STATIC_ROOT = config.get('django','static_root')

MEDIA_URL = config.get('django','media_url')
MEDIA_ROOT = config.get('django','media_root')

STATICFILES_DIRS = [
    config.get('django','static_local'),
    config.get('django','dedup_root'),
]

# since PlasTeX produces many static files that are repeated in each blob HTML version, they are copied here 
DEDUP_ROOT = config.get('django','dedup_root')
# and served here
DEDUP_URL = config.get('django','dedup_url')

## https://codemirror.net/
USE_CODEMIRROR = os.path.isdir(os.path.join(BASE_DIR, '..', 'node_modules', 'codemirror'))
if not USE_CODEMIRROR:
    logger.warning('You may want to install CodeMirror, use `bin/install_CodeMirror.sh`')

# you can overwrite this in the settings.py file in the deployed COLDOC_SITE_ROOT
GOOGLE_SITE_VERIFICATION =  None
GOOGLE_ANALYTICS4 = None

# you can overwrite this in the settings.py file in the deployed COLDOC_SITE_ROOT
# define these to use Microsoft Azure translation service
AZURE_SUBSCRIPTION_KEY = None
AZURE_LOCATION = None

######################### pricing scheme for this coldoc; see settings_suggested for examples

def PRICE_FOR_PERMISSION(user, blob, permission ):
    return 'No permissions can be bought'

######################### include settings_local

try:
    from settings_local import *
    logger.debug('loaded settings_local')
except ImportError:
    pass
except:
    logger.exception("Error importing `settings_local`")

######################### include settings for deployed site

if COLDOC_SITE_ROOT is None:
    logger.debug('Environ COLDOC_SITE_ROOT not set')
else:
    COLDOC_SITE_SETTINGS = os.path.join(COLDOC_SITE_ROOT,'settings.py')
    if os.path.isfile(COLDOC_SITE_SETTINGS):
        try:
            exec(compile(open(COLDOC_SITE_SETTINGS).read(),COLDOC_SITE_SETTINGS,'exec'))
        except:
            logger.exception('While executing %r',COLDOC_SITE_SETTINGS)
    else:
        logger.warning('No such file: %r',COLDOC_SITE_SETTINGS)
        COLDOC_SITE_SETTINGS = False


# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


if (RECAPTCHA_PUBLIC_KEY is None or RECAPTCHA_PRIVATE_KEY is  None) and USE_RECAPTCHA:
    logger.warning('USE_RECAPTCHA is True but RECAPTCHA_PUBLIC_KEY or RECAPTCHA_PRIVATE_KEY are not defined: disabled')
    USE_RECAPTCHA = False

if USE_SIMPLE_CAPTCHA and USE_RECAPTCHA:
    logger.warning('SIMPLE_CAPTCHA and RECAPTCHA cannot be used at the same time, disabling one of the two')
    USE_RECAPTCHA = bool(RECAPTCHA_PUBLIC_KEY)

TRANSLATOR = None

if AZURE_SUBSCRIPTION_KEY and AZURE_LOCATION:
    def TRANSLATOR(text, fromlang, tolang):
        from ColDocDjango.translators import translator_Azure
        return translator_Azure(text, fromlang, tolang, AZURE_SUBSCRIPTION_KEY, AZURE_LOCATION)
