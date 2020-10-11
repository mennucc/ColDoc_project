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

COLDOC_SITE_CONFIG = config = get_config()

COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config['django'].getboolean('debug')


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

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    #https://docs.djangoproject.com/en/3.0/howto/static-files/
    'django.contrib.staticfiles',
    'ColDocDjango.ColDocApp',
    'ColDocDjango.UUID',
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

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
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
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # https://github.com/bugov/django-custom-anonymous
    'ColDocDjango.custom_anonymous.AuthenticationMiddleware',
]

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
]


try:
    from ColDocDjango.settings_local import *
    logger.debug('loaded settings_local')
except ImportError:
    pass
except:
    logger.warning("Error importing ColDocDjango.settings_local")


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


