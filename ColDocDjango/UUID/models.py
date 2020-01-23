import os
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models
from django.core.validators  import RegexValidator

from ColDocDjango import settings

from ColDocDjango.ColDocApp.models import DColDoc, UUID_Field

from ColDoc import classes, utils as coldoc_utils

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
            self._basepath = kwargs['basepath']
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
    ####
    # these calls implement part of the interface `classes.MetadataBase`
    #
    @classmethod
    def load_by_uuid(cls, uuid, coldoc=None, basepath=None):
        " returns an instance that matches the `uuid` in the `coldoc` or in the `basepath`"
        if isinstance(uuid,str):
            uuid = coldoc_utils.uuid_to_int(uuid)
        r = DMetadata.objects.filter(uuid=uuid,coldoc=coldoc)
        l = len(r)
        if l == 0 :
            logger.warning('No DMetadata for uuid=%r coldoc=%r'%(coldoc_utils.int_to_uuid(uuid),coldoc))
            return None
        elif l > 1:
            logger.warning('Multiple DMetadata for uuid=%r coldoc=%r'%(coldoc_utils.int_to_uuid(uuid),coldoc))
        for j in r:
            return j
    #
    def __write(self):
        "write a file with all metadata (as `FMetadata` does, used by non-django blob_inator) for easy inspection and comparison"
        if self.coldoc.directory is None:
            coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',self.coldoc.nickname,'blobs')
        else:
            coldoc_dir = self.coldoc.directory
            if os.path.isabs(coldoc_dir):
                coldoc_dir = osjoin(COLDOC_SITE_ROOT, coldoc_dir)
        blobs_dir = osjoin(coldoc_dir, 'blobs')
        #
        F = osjoin(blobs_dir, coldoc_utils.uuid_to_dir(self.uuid, blobs_dir=blobs_dir), 'metadata')
        #logger.debug
        F = open(F,'w')
        F.write( 'coldoc=' + self.coldoc.nickname + '\n')
        for key in  ('uuid', 'environ'):
            F.write( key + '=' + getattr(self,key) + '\n')
        for key in ('extension','lang','authors'):
            for value in getattr(self,key).split('\n'):
                F.write( key + '=' + value + '\n')
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid):
            F.write( 'parent_uuid=' + obj.parent + '\n')
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid):
            F.write( 'child_uuid=' + obj.child + '\n')
        for obj in ExtraMetadata.objects.filter(blob=self):
            F.write( obj.key + '=' + obj.value + '\n')
        F.close()
    #
    def save(self):
        r = super().save()
        for c in self._children:
            if not UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid, child = c).exists():
                UUID_Tree_Edge(coldoc = self.coldoc, parent = self.uuid, child = c).save()
        self._children = []
        # no need to save parents...
        for p in self._parents:
            if not UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = p, child = self.uuid).exists():
                UUID_Tree_Edge(coldoc = self.coldoc, parent = p, child = self.uuid).save()
        self._parents = []
        #
        for k,v in self._extra_metadata:
            if not ExtraMetadata.objects.filter(blob = self, key =  k, value = v).exists():
                ExtraMetadata(blob = self, key =  k, value = v).save()
        self._extra_metadata = []
        #
        self.__write()
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
            v = v.split('\n')
            if value not in v:
                v.append(value)
            setattr(self, key, '\n'.join(v))
        elif key == 'child_uuid' and value not in self._children:
            self._children.append(value)
        elif key == 'parent_uuid' and value not in self._parents:
            self._parents.append(value)
        elif (key,value) not in self._extra_metadata:
            self._extra_metadata.append((key,value))
    #
    def __setitem__(self,key,value):
        " set value `value` for `key` (as one single value, even if multivalued)"
        if key in  ('uuid','environ','extension','lang','authors'):
            setattr(self, key, value)
        elif key in ('child_uuid', 'parent_uuid'):
            raise NotImplementedError()
        else:
            raise NotImplementedError()


class ExtraMetadata(models.Model):
    blob = models.ForeignKey(DMetadata, on_delete=models.CASCADE, db_index = True)
    key = models.SlugField(max_length=80, db_index = True)
    value = models.CharField(max_length=120, db_index = True, blank=True)

