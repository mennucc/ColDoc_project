import os
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models
from django.core.validators  import RegexValidator
from django.urls import reverse

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
    #
    def get_absolute_url(self):
        return reverse('UUID:index', args=(self.coldoc.nickname,self.uuid))
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    uuid = UUID_Field(db_index = True, )
    environ = models.CharField(max_length=100, db_index = True)
    extension = models.TextField(max_length=100,help_text="newline-separated list of extensions",
                                 default='', blank=True)
    lang = models.TextField(max_length=100,help_text="newline-eparated list of languages",
                            default='', blank=True)
    #
    authors = models.TextField('newline-separated list of authors',max_length=10000,
                               default='', blank=True)
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
    def load_by_uuid(cls, uuid, coldoc, basepath=None):
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
        coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',self.coldoc.nickname)
        blobs_dir = osjoin(coldoc_dir, 'blobs')
        #
        F = osjoin(blobs_dir, coldoc_utils.uuid_to_dir(self.uuid, blobs_dir=blobs_dir), 'metadata')
        #logger.debug
        F = open(F,'w')
        F.write( 'coldoc=' + self.coldoc.nickname + '\n')
        for k,vv in self.items():
            for v in vv:
                F.write( k + '=' + v + '\n')
        F.close()
    #
    def __key_to_list(self,key):
        v = getattr(self,key)
        if not v:
            return []
        l = v.splitlines()
        return l
    #
    def singled_items(self):
        " yields all (key,value) pairs, where each `key` may be repeated multiple times"
        for key in  ('uuid', 'environ'):
            yield key, getattr(self,key)
        for key in ('extension','lang','authors'):
            l = self.__key_to_list(key)
            for value in l:
                yield key, value
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid):
            yield 'parent_uuid', obj.parent
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid):
            yield 'child_uuid', obj.child
        for obj in ExtraMetadata.objects.filter(blob=self):
            yield obj.key, obj.value
    #
    def save(self):
        for k in ('extension','lang','authors'):
            v = getattr(self,k)
            v = v.replace('\r','')
            if v and v[-1] != '\n':
                logger.warning('save: UUID %r key %r was missing final newline: %r',self.uuid,k,v)
                v += '\n'
            setattr(self,k, v)
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
            assert '\n' not in value
            v = self.__key_to_list(key)
            if value not in v:
                v.append(value)
            setattr(self, key, '\n'.join(v)+'\n')
        elif key == 'child_uuid' and value not in self._children:
            self._children.append(value)
        elif key == 'parent_uuid' and value not in self._parents:
            self._parents.append(value)
        elif (key,value) not in self._extra_metadata:
            self._extra_metadata.append((key,value))
    #
    def __setitem__(self,key,value):
        " set value `value` for `key` (as one single value, even if multivalued)"
        if key in  ('uuid','environ'):
            setattr(self, key, value)
        elif key in  ('extension','lang','authors'):
            assert '\n' not in value
            setattr(self, key, value+'\n')
        elif key in ('child_uuid', 'parent_uuid'):
            raise NotImplementedError()
        else:
            raise NotImplementedError()
    #
    def get(self, key, default = None):
        "returns a list of all values associated to `key` ; it returns the list even when `key` is known to be singlevalued"
        if default is not None:
            logger.error('DMetadat.get default is not implemented, key=%r',key)
        if key in  ('uuid','environ'):
            return [getattr(self, key)]
        elif key in ('extension','lang','authors'):
            return self.__key_to_list(key)
        elif key == 'parent_uuid':
            return UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid).values_list('parent', flat=True)
        elif key == 'child_uuid':
            return UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid).values_list('child', flat=True)
        else:
            return ExtraMetadata.objects.filter(blob=self, key=key).values_list('value', flat=True)
    #
    #
    def items(self, serve_empty=False):
        "returns (key, values)"
        for key in  ('uuid','environ'):
            yield key, [getattr(self, key)]
        for key in ('extension','lang','authors'):
            l = self.__key_to_list(key)
            if l or serve_empty:
                yield key, l
        #key == 'parent_uuid':
        yield 'parent_uuid', UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid).values_list('parent',flat=True)
        #key == 'child_uuid':
        yield 'child_uuid', UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid).values_list('child',flat=True)
        seen = set()
        for key in ExtraMetadata.objects.filter(blob=self).values_list('key', flat=True):
            if key not in seen:
                yield key, ExtraMetadata.objects.filter(blob=self, key=key).values_list('value', flat=True)
            seen.add(key)
    #
    def htmlitems(self):
        return coldoc_utils.metadata_html_items(self, self.coldoc.nickname)

class ExtraMetadata(models.Model):
    blob = models.ForeignKey(DMetadata, on_delete=models.CASCADE, db_index = True)
    key = models.SlugField(max_length=80, db_index = True)
    value = models.CharField(max_length=120, db_index = True, blank=True)

