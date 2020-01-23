import os
from os.path import join as osjoin

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models
from django.core.validators  import RegexValidator

from ColDocDjango import settings

from ColDocDjango.ColDocApp.models import DColDoc, UUID_Field

# Create your models here.

COLDOC_SITE_ROOT = os.environ['COLDOC_SITE_ROOT']

class UUID_Tree_Edge(models.Model):
    "edges for the graph parent-child of blobs in a coldoc"
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    parent = UUID_Field(db_index = True)
    child = UUID_Field(db_index = True)

class DMetadata(models.Model): # cannot add `classes.MetadataBase`, it interferes with the Django magick
    "Metadata of a blob, stored in the Django databases, and also in a file (for easy access)"
    #
    def __init__(self, *args, **kwargs):
        self._extra_metadata = []
        self._children = []
        self._parents = []
        if 'basepath' in kwargs:
            self.__basepath = kwargs['basepath']
            del kwargs['basepath']
        # these keys are single valued
        self._single_valued_keys = ('uuid','environ')
        assert self._single_valued_keys == classes.MetadataBase._single_valued_keys
        # these keys are multiple-valued, are internal, are represented
        # as a newline-separated text field
        self._internal_multiple_valued_keys = ('extension','lang','authors')
        #
        super().__init__(*args, **kwargs)

        #self.coldoc = coldoc
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    uuid = UUID_Field(db_index = True, )
    environ = models.CharField(max_length=100, db_index = True)
    extension = models.TextField(max_length=100,help_text="newline-eparated list of extensions",
                                 default='', blank=True)
    lang = models.TextField(max_length=100,help_text="newline-eparated list of languages",
                            default='', blank=True)
    #
    authors = models.TextField('newline-separated list of authors',max_length=10000)
    creation_date = models.DateTimeField('date of creation', default=DT.now)
    modification_date = models.DateTimeField('date of last modification', default=DT.now)
    #
    BLOB_DOCUMENTCLASS=[
        ('auto','use `main` class for sections and whole document, `standalone` class for others'),
        ('main','use the class of the main document (usually associated to UUID 001)'),
        ('standalone','use `standalone` documentclass'),
        ('article','use `article` documentclass'),
        ('book','use `book` documentclass'),
    ]
    latex_documentclass = models.CharField("documentclass used to compile", max_length=15,
                                           choices=BLOB_DOCUMENTCLASS,        default='auto')
    # these calls are shared with the non-django blob_inator
    #
    def write(self):
        r = self.save()
        for c in self._children:
            UUID_Tree_Edge(coldoc = self.coldoc, parent = self.uuid, child = c).save()
        self._children = []
        # no need to save parents...
        self._parents = []
        #
        for k,v in self._extra_metadata:
            ExtraMetadata(uuid = self, key =  k, value = v).save()
        self._extra_metadata = []
        #
        return r
    #
    def add(self, key, value):
        """ for single valued `key`, set `value`; for multiple value,
        add the `value` as a possible value for `key` (only if the value is not present) ;
        this call is used by the blob_inator"""
        if key in  ('uuid','environ'):
            setattr(self, key, value)
        elif key in ('extension','lang','authors'):
            v = getattr(self,key)
            if v:
                v += '\n'
            v += value
            setattr(self, key, v)
        elif key == 'child_uuid':
            self._children.append(value)
        elif key == 'parent_uuid':
            self._parents.append(value)
        else:
            self._extra_metadata.append((key,value))

class ExtraMetadata(models.Model):
    blob = models.ForeignKey(DMetadata, on_delete=models.CASCADE, db_index = True)
    key = models.SlugField(max_length=80, db_index = True)
    value = models.CharField(max_length=120, db_index = True, blank=True)

