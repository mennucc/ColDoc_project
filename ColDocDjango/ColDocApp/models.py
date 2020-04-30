import os
from os.path import join as osjoin

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models
from django import forms
from django.core.validators  import RegexValidator
import django.core.exceptions
from django.core import serializers
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.conf import settings

# TODO : site support
# from django.contrib.sites.models import Site


import logging
logger = logging.getLogger(__name__)

def _(s):
    return s

#############################################################

from ColDoc.utils import uuid_to_int, int_to_uuid, uuid_check_normalize, uuid_valid_symbols
from ColDoc.latex import ColDoc_latex_engines
import ColDoc.config

from ColDocDjango.users import permissions_for_coldoc

#####################################


## we cannot user this, it is too early
#from django.contrib.auth import get_user_model
#AUTH_USER_MODEL = get_user_model()
## su we use this
AUTH_USER_MODEL = settings.AUTH_USER_MODEL



#####################################

class UUID_FormField(forms.CharField):
    ## TODO FIXME THIS DOES NOT WORK AS EXPECTED
    default_error_messages = {
        'invalid': 'Enter a valid UUID (numbers and consonants)',
    }
    def clean(self, value):
        if (not (value == '' and not self.required) and   not uuid_valid_symbols.match(value)):
            raise forms.ValidationError(self.error_messages['invalid'])
        return value


validate_UUID = RegexValidator(
    uuid_valid_symbols,
    # Translators: "letters" means latin letters: a-z and A-Z.
    _("Enter a valid 'UUID' consisting of numbers and consonants"),
    'invalid'
)
# https://docs.djangoproject.com/en/3.0/howto/custom-model-fields/
class UUID_Field(models.IntegerField):
    default_error_messages = {
        'invalid': _("'%(value)s' value must be a ColDoc UUID."),
    }
    description = _("ColDoc UUID")
    default_validators = [validate_UUID]
    #
    def to_python(self, value):
        if isinstance(value, str) or value is None:
            return value
        else:
            return int_to_uuid(obj)
    #
    def from_db_value(self, obj, expression, connection):
        if isinstance(obj, int):
            return int_to_uuid(obj)
        elif isinstance(obj, str):
            return uuid_check_normalize(obj)
        else:
            raise ValueError(" wrong type %r"%(type(obj),))
    #
    def get_prep_value(self,value):
        if isinstance(value,int):
            return value
        assert isinstance(value,str)
        try:
            return uuid_to_int(value)
        except (TypeError, ValueError):
            raise exceptions.ValidationError(
                'Invalid UUID',
                code='invalid',
                params={'value': value},
            )
    #
    def formfield(self, **kwargs):
        kwargs['form_class'] = UUID_FormField
        return models.fields.Field.formfield(self, **kwargs)
        #return super().formfield(**kwargs)

# Create your models here.

COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')

def validate_coldoc_nickname(value):
    if value in ColDoc.config.ColDoc_invalid_nickname :
        raise ValidationError(
            _('Please do not use %(value)s as nickname, it may generate confusion'),
            params={'value': value},
        )

class DColDoc(models.Model):
    "Collaborative Document"
    #
    class Meta:
        verbose_name = "ColDoc"
        permissions = [(j,"can %s on any coldoc"%j) for j in permissions_for_coldoc]
    #https://docs.djangoproject.com/en/3.0/ref/urlresolvers/#django.urls.reverse
    #https://docs.djangoproject.com/en/3.0/ref/models/instances/#django.db.models.Model.get_absolute_url
    def get_absolute_url(self):
        return reverse('ColDoc:index', args=(self.nickname,))
    #  https://docs.djangoproject.com/en/3.0/ref/models/fields
    nickname = models.SlugField("short string to identify",
                                help_text="short string to identify this ColDoc in URLs (alphanumeric only, use '_' or '-' for other chars)",
                                validators=[validate_coldoc_nickname],
                                max_length=10,  db_index = True, primary_key=True)
    #
    title = models.CharField(max_length=2000, blank=True)
    editor = models.ManyToManyField(AUTH_USER_MODEL)
    abstract = models.TextField(max_length=10000, blank=True)
    #
    publication_time = models.DateTimeField('time first published', default=DT.now)
    #
    ## TODO
    #modification_time = models.DateTimeField('time of last modification', default=DT.now)
    #def modification_time_update(self, default=None):
    #    if default is None: default=DT.now()
    #    self.modification_time = default
    #
    blob_modification_time = models.DateTimeField('time of last modification of any blob in this coldoc', default=DT.now)
    def blob_modification_time_update(self, default=None):
        if default is None: default=DT.now()
        self.blob_modification_time = default
    #
    latex_time = models.DateTimeField('time of last run of latex',
                                      default=None, null=True)
    def latex_time_update(self, default=None):
        if default is None: default=DT.now()
        self.latex_time = default
    # blank means that no error occoured
    latex_return_codes = models.CharField(max_length=2000, blank=True)
    #
    anonymous_can_view = models.BooleanField(default=True)
    #
    LATEX_ENGINES=ColDoc_latex_engines
    latex_engine = models.CharField("latex-type command used to compile",
        max_length=15,
        choices=LATEX_ENGINES,
        default='pdflatex',
    )
    #
    root_uuid = UUID_Field(default=1)
    #
    def save(self):
        ## TODO should update only if something was changed.. use signals?
        #try:
        #    self.modification_date_update()
        #except:
        #    logger.exception()
        r = super().save()
        if COLDOC_SITE_ROOT is None:
            raise RuntimeError("Cannot save, COLDOC_SITE_ROOT==None: %r",self)
        coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',self.nickname)
        if not os.path.exists(coldoc_dir):
            os.makedirs(coldoc_dir)
        data = serializers.serialize("json", [self])
        assert data[0] == '[' and data[-1]==']'
        open(osjoin(coldoc_dir,'coldoc.json'),'w').write(data[1:-1])
    #
    #def get_fields(self):
    #    return [(field.name, field.value_to_string(self)) for field in DColDoc._meta.fields]
    #### making these customizable is overkill and useless
    #
    #def base_path(s):
    #    return osjoin(COLDOC_SITE_ROOT,s.nickname)
    #base_path = osjoin(COLDOC_SITE_ROOT,'coldoc')
    #
    #git_master_dir = models.FilePathField("directory for the `git` bare repository",
    #                                      path=base_path, default='git',
    #                                      allow_folders = True, allow_files = False)
    #blobs_user_dirs = models.FilePathField("directory under which the `git` bare repository is checked out, for each user wishing to modify it",
    #                                        path=base_path, default='users',
    #                                        allow_folders = True, allow_files = False)
    #blobs_anon_dir = models.FilePathField("directory where the `git` bare repository is checked out, but masking private blobs",
    #                                      path=base_path, default='anon',
    #                                      allow_folders = True, allow_files = False)

