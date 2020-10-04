import os
from os.path import join as osjoin

import logging
logger = logging.getLogger(__name__)

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models
from django.core.validators  import RegexValidator
from django.urls import reverse

from django.conf import settings
AUTH_USER_MODEL = settings.AUTH_USER_MODEL

from ColDocDjango.ColDocApp.models import DColDoc, UUID_Field


from ColDoc import classes, utils as coldoc_utils

from ColDoc.classes import DuplicateLabel

from ColDocDjango.users import ColDocUser, permissions_for_blob_extra

# Create your models here.

COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')

class UUID_Tree_Edge(models.Model):
    "edges for the graph parent-child of blobs in a coldoc"
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    parent = UUID_Field(db_index = True)
    child = UUID_Field(db_index = True)

#class UUID_Tree_Edge_(models.Model):
#    "edges for the graph parent-child of blobs in a coldoc"
#    # this would be much cooler..
#    parent = models.ForeignKey(BlobMetadata, on_delete=models.CASCADE, db_index = True)
#    child = models.ForeignKey(BlobMetadata, on_delete=models.CASCADE, db_index = True)


class DMetadata(models.Model): # cannot add `classes.MetadataBase`, it interferes with the Django magick
    "Metadata of a blob, stored in the Django databases, and also in a file (for easy access)"
    #
    ## Data stored in this Model are so classified:
    # -) these keys are multiple-valued, each value is a text line, are represented 
    # as a newline-separated text field
    __internal_multiple_valued_keys = ('extension','lang')
    # -) these are singled-value and are internal
    __single_valued = ('id', 'coldoc', 'uuid', 'environ', 'optarg', 'original_filename',
                       'latex_documentclass_choice', 'access',
                       'creation_time','blob_modification_time','latex_time','latex_return_codes')
    # -) then there is 'author' that is a ManyToMany,
    # -) some fields cannot be changed or deleted
    __protected_fields = 'id', 'coldoc', 'uuid'
    # all other key/value pairs are stored in 'extrametadata', that is a ManyToMany to    ExtraMetadata
    #
    class Meta:
        verbose_name = "Metadata"
        permissions = [(j,"can %s anywhere"%j) for j in permissions_for_blob_extra]
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
        #
        super().__init__(*args, **kwargs)
        if settings.DEBUG:
            a = set(self.__internal_multiple_valued_keys)
            a.update(set(self.__single_valued))
            a.add('author')
            a.add('extrametadata')
            b = set(a.name for a in self._meta.get_fields())
            if a != b:
                logger.warning('DMetadata fields unaliagned, a="documented" b="effective": a-b %r b-a %r'%( a.difference(b), b.difference(a) ))
    #
    def get_absolute_url(self):
        return reverse('UUID:index', args=(self.coldoc.nickname,self.uuid))
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    uuid = UUID_Field(db_index = True, )
    environ = models.CharField(max_length=100, db_index = True, blank=True)
    optarg = models.CharField(max_length=300, blank=True)
    extension = models.TextField(max_length=100,help_text="newline-separated list of extensions",
                                 default='', blank=True)
    lang = models.TextField(max_length=100,help_text="newline-separated list of languages",
                            default='', blank=True)
    original_filename = models.CharField(max_length=1000, blank=True,
                                         help_text="the filename whose content was copied in this blob (and children of this blob)")
    #
    author = models.ManyToManyField(AUTH_USER_MODEL)
    #
    creation_time = models.DateTimeField('date of creation', default=DT.now)
    #
    blob_modification_time = models.DateTimeField('time of last modification of content',
                                                  default=None, null=True)
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
    # used for permissions, see utils.user_has_perm()
    ACCESS_CHOICES = [('open','view and LaTeX visible to everybody'),
              ('public','view visible to everybody, LaTeX restricted'),
              ('private','visible only to editors, and authors of this blob')]
    access = models.CharField("access", max_length=15,
                              choices=ACCESS_CHOICES,    default='public')
    #
    BLOB_DOCUMENTCLASS=[
        ('auto','use `main` class for sections and whole document, `standalone` class for others'),
        ('main','use the class of the main document (usually associated to UUID 001)'),
        ('standalone','use `standalone` documentclass'),
        ('article','use `article` documentclass'),
        ('book','use `book` documentclass'),
    ]
    latex_documentclass_choice = models.CharField("documentclass used to compile", max_length=15,
                                           choices=BLOB_DOCUMENTCLASS,   default='auto')
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
        if COLDOC_SITE_ROOT is None:
            raise RuntimeError("Cannot save, COLDOC_SITE_ROOT==None: %r",self)
        coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',self.coldoc.nickname)
        blobs_dir = osjoin(coldoc_dir, 'blobs')
        #
        F = osjoin(blobs_dir, coldoc_utils.uuid_to_dir(self.uuid, blobs_dir=blobs_dir))
        if not os.path.exists(F):
            os.makedirs(F)
        F = osjoin(F, 'metadata')
        F = open(F,'w')
        F.write( 'coldoc=' + self.coldoc.nickname + '\n')
        for k,vv in self.items():
            for v in vv:
                if isinstance(v, ColDocUser):
                    v = v.username
                F.write( k + '=' + str(v) + '\n')
        F.write('saved_by_django=True')
        F.close()
    #
    def __key_to_list(self,key):
        assert key in self.__internal_multiple_valued_keys
        v = getattr(self,key)
        if not v:
            return []
        l = v.splitlines()
        return l
    #
    def singled_items(self):
        " yields all (key,value) pairs, where each `key` may be repeated multiple times"
        for key in  self.__single_valued:
            yield key, getattr(self,key)
        for key in self.__internal_multiple_valued_keys:
            l = self.__key_to_list(key)
            for value in l:
                yield key, value
        for value in self.author.all():
            return 'author', value
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid):
            yield 'parent_uuid', obj.parent
        for obj in  UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid):
            yield 'child_uuid', obj.child
        for obj in ExtraMetadata.objects.filter(blob=self):
            yield obj.key, obj.value
    #
    def save(self):
        for k in self.__internal_multiple_valued_keys:
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
        if key in self.__protected_fields:
            raise RuntimeError('Cannot set protected field %r to %r'%(key, value))
        if key in  self.__single_valued:
            setattr(self, key, value)
        elif key in self.__internal_multiple_valued_keys:
            assert '\n' not in value
            v = self.__key_to_list(key)
            if value not in v:
                v.append(value)
            setattr(self, key, '\n'.join(v)+'\n')
        elif key == 'author' :
            if isinstance(value,str):
                value = ColDocUser.objects.get(username=value)
            self.author.add(value)
        elif key == 'child_uuid' and value not in self._children:
            self._children.append(value)
        elif key == 'parent_uuid' and value not in self._parents:
            self._parents.append(value)
        else:
            if (key,value) not in self._extra_metadata:
                self._extra_metadata.append((key,value))
            elif key.endswith('M_label'):
                logger.warning('Duplicate key/value %r = %r',key,value)
                ## this will print more info: filename, line, UUID
                raise DuplicateLabel('Duplicate key/value %r = %r'% (key,value))
    #
    def __setitem__(self,key,value):
        " set value `value` for `key` (as one single value, even if multivalued)"
        if key in  self.__single_valued:
            setattr(self, key, value)
        elif key in  self.__internal_multiple_valued_keys:
            assert '\n' not in value
            setattr(self, key, value+'\n')
        elif key in ('child_uuid', 'parent_uuid', 'author'):
            #it is somewhat pointless
            raise NotImplementedError()
        else:
            raise NotImplementedError()
    #
    def get(self, key, default = None):
        """returns a list of all values associated to `key` ; it returns the list even when `key` is known to be singlevalued"""
        if default is not None:
            logger.error('DMetadata.get default is not implemented, key=%r',key)
        if key in  self.__single_valued:
            return [getattr(self, key)]
        elif key in self.__internal_multiple_valued_keys:
            return self.__key_to_list(key)
        elif key == 'author':
            return self.author.all().values_list('username', flat = True)
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
        for key in  self.__single_valued:
            yield key, [getattr(self, key)]
        for key in self.__internal_multiple_valued_keys:
            l = self.__key_to_list(key)
            if l or serve_empty:
                yield key, l
        #key == 'author':
        yield 'author', self.author.all().values_list('username', flat = True)
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

