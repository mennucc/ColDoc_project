import os
from os.path import join as osjoin
import re

import logging
logger = logging.getLogger(__name__)

#from datetime import datetime as DT
from django.utils import timezone as DT

from django.db import models, transaction
from django.db.models import Q as advanced_query
#from django.core.validators  import RegexValidator
from django.urls import reverse
#from django.templatetags.static import static

from django.conf import settings
AUTH_USER_MODEL = settings.AUTH_USER_MODEL

from django.utils.translation import gettext, gettext_lazy, gettext_noop
_ = gettext_lazy

from ColDocApp.models import DColDoc, UUID_Field


from ColDoc import classes, utils as coldoc_utils

from ColDoc.classes import DuplicateLabel

from ColDocDjango.users import ColDocUser, permissions_for_blob_extra

# Create your models here.

COLDOC_SITE_ROOT = os.environ.get('COLDOC_SITE_ROOT')

class UUID_Tree_Edge(models.Model):
    "edges for the graph parent-child of blobs in a coldoc"
    class Meta:
        ordering = ['coldoc','parent','child_ordering','child']
    #
    coldoc = models.ForeignKey(DColDoc, on_delete=models.CASCADE, db_index = True)
    parent = UUID_Field(db_index = True)
    child = UUID_Field(db_index = True)
    child_ordering = models.IntegerField(_("used to order the children as in the TeX"),default=0)

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
                       'order_in_document',
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
            b = set(j.name for j in self._meta.get_fields())
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
    extension = models.TextField(max_length=100,help_text=_("newline-separated list of extensions"),
                                 default='', blank=True)
    lang = models.TextField(max_length=100,help_text=_("newline-separated list of languages"),
                            default='', blank=True)
    original_filename = models.CharField(max_length=1000, blank=True,
                                         help_text=_("the filename whose content was copied in this blob (and children of this blob)"))
    #
    author = models.ManyToManyField(AUTH_USER_MODEL)
    #
    creation_time = models.DateTimeField(_('date of creation'), default=DT.now)
    #
    blob_modification_time = models.DateTimeField(_('time of last modification of content'),
                                                  default=None, null=True)
    def blob_modification_time_update(self, default=None):
        if default is None: default=DT.now()
        self.blob_modification_time = default
        self.save()
        self.coldoc.blob_modification_time_update(default)
    #
    latex_time = models.DateTimeField(_('time of last run of latex'),
                                      default=None, null=True, blank=True)
    def latex_time_update(self, default=None):
        if default is None: default=DT.now()
        self.latex_time = default
        self.save()
        self.coldoc.latex_time_update(default)
    # blank means that no error occoured
    latex_return_codes = models.CharField(max_length=2000, blank=True)
    #
    # used for permissions, see utils.user_has_perm()
    ACCESS_CHOICES = [('open', _('view and LaTeX visible to everybody')),
              ('public', _('view visible to everybody, LaTeX restricted')),
              ('private', _('visible only to editors, and authors of this blob'))]
    access = models.CharField(_("access policy"), max_length=15,
                              choices=ACCESS_CHOICES,    default='public')
    #
    BLOB_DOCUMENTCLASS=[
        ('auto', _('use `main` class for sections and whole document, `standalone` class for others')),
        ('main', _('use the class of the main document (usually associated to UUID 001)')),
        ('standalone', _('use `standalone` documentclass')),
        ('article', _('use `article` documentclass')),
        ('book', _('use `book` documentclass')),
    ]
    latex_documentclass_choice = models.CharField(_("documentclass used to compile"), max_length=15,
                                           choices=BLOB_DOCUMENTCLASS,   default='auto')
    #
    order_in_document = models.PositiveIntegerField(_('enumerates blobs in the order in which they appear in the document'),
                                                    default=0x7fffffff )
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
    def locked_fresh_copy(self):
        " Returns a copy of the object that is locked for database update. "
        return DMetadata.objects.select_for_update().get(pk=self.pk)
    #
    def transaction_atomic(self):
        return transaction.atomic()
    #
    def backup_filename(self):
        if COLDOC_SITE_ROOT is None:
            raise RuntimeError("Cannot save, COLDOC_SITE_ROOT==None: %r",self)
        coldoc_dir = osjoin(COLDOC_SITE_ROOT,'coldocs',self.coldoc.nickname)
        blobs_dir = osjoin(coldoc_dir, 'blobs')
        #
        F = osjoin(blobs_dir, coldoc_utils.uuid_to_dir(self.uuid, blobs_dir=blobs_dir))
        if not os.path.exists(F):
            os.makedirs(F)
        return osjoin(F, 'metadata')
    #
    def __write(self):
        "write a file with all metadata (as `FMetadata` does, used by non-django blob_inator) for easy inspection and comparison"
        F = open(self.backup_filename(),'w')
        F.write( 'coldoc=' + self.coldoc.nickname + '\n')
        for k,vv in self.items():
            if k == 'coldoc':
                continue
            for v in vv:
                if isinstance(v, ColDocUser):
                    v = v.username
                F.write( k + '=' + str(v) + '\n')
        for k,vv in self.items2():
            for v1,v2 in vv:
                F.write( k + '=' + str(v1) + '\t' + str(v2) + '\n')
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
    def save(self, *save_args, **save_kwargs):
        if settings.DEBUG:
            for k in self.__internal_multiple_valued_keys:
                v = getattr(self, k)
                if (v and v[-1] != '\n') or '\r' in v:
                    logger.debug('save: UUID %r key %r missing final newline, or contains \\r: %r',self.uuid,k,v)
        #
        r = super().save(*save_args, **save_kwargs)
        #
        if self._children:
            a = UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid).values_list('child_ordering', flat=True)
            j = max( a, default=0 ) + 1
            for n,c in enumerate(self._children):
                if not UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid, child = c).exists():
                    UUID_Tree_Edge(coldoc = self.coldoc, parent = self.uuid, child = c, child_ordering=(n+j)).save()
                else:
                    logger.debug("Duplicate children %r for parent %r",c,self.uuid)
            self._children = []
        # no need to save parents...
        for p in self._parents:
            # fixme, here we do not know the correct ordering, so we set us last
            if not UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = p, child = self.uuid).exists():
                a = UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = p).values_list('child_ordering', flat=True)
                j = max( a, default=0 )
                UUID_Tree_Edge(coldoc = self.coldoc, parent = p, child = self.uuid, child_ordering=(j+1)).save()
            else:
                logger.debug("Parent %r for child %r already registered",p,self.uuid)
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
    def __delitem__(self,key):
        "delete all values for `key`"
        if key in  self.__single_valued or key in self.__internal_multiple_valued_keys:
            raise NotImplementedError()
        if key == 'child_uuid':
            UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid).delete()
        elif key == 'parent_uuid':
            logger.warning('delete all parent relationship for %r ',self)
            UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid).delete()
        else:
            ExtraMetadata.objects.filter(blob=self, key=key).delete()
    #
    def delete(self,key,value):
        "delete a key/value"
        if key in  self.__single_valued or key in self.__internal_multiple_valued_keys:
            raise NotImplementedError()
        if key == 'child_uuid':
            UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, parent = self.uuid, child=value).delete()
        elif key == 'parent_uuid': 
            UUID_Tree_Edge.objects.filter(coldoc=self.coldoc, child = self.uuid, parent=value).delete()
        else:
            ExtraMetadata.objects.filter(blob=self, key=key, value=value).delete()
    #
    def get2(self, key, withvalue=None, default = None):
        " get extrametadata with two values, such as AUX_label ; filter by `withvalue` if present ; return list of pairs"
        o = ExtraMetadata.objects.filter(blob=self, key=key)
        if withvalue:
            o = o.filter(value=withvalue)
        return o.values_list('value', 'second_value')
    def delete2(self,key,withvalue=None):
        o = ExtraMetadata.objects.filter(blob=self, key=key)
        if withvalue:
            o = o.filter(value=withvalue)
        o.delete()
    def add2(self, key, value, second_value):
        ExtraMetadata(blob = self, key =  key, value = value, second_value = second_value).save()
    def items2(self):
        " yields key,[(a1,a2),(b1,b2),(c1,c2),...] "
        seen = set()
        for key in ExtraMetadata.objects.filter(blob=self).exclude(second_value=None).values_list('key', flat=True):
            if key not in seen:
                yield key, ExtraMetadata.objects.filter(blob=self, key=key).exclude(second_value=None).values_list('value', 'second_value')
            seen.add(key)
    #
    def get(self, key, default = None):
        """returns a list of all values associated to `key` ; it returns the list even when `key` is known to be singlevalued"""
        if default is not None:
            logger.error('DMetadata.get default is not implemented, key=%r',key)
        if key in  self.__single_valued:
            return [getattr(self, key)]
        elif key == 'lang' :
            return self.get_languages()
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
    def get_languages(self):
        " return list of languages, correctly formatted"
        L = self.lang.splitlines()
        if any([ (len(z)!=3) for z in L]):
            logger.warning('Malformed languages %r in %s', self.lang, self)
        return [z for z in L if len(z) == 3]
    #
    def keys(self):
        "returns keys without repetitions"
        for key in  self.__single_valued:
            yield key
        for key in self.__internal_multiple_valued_keys:
            yield key
        yield 'author'
        yield 'parent_uuid'
        yield 'child_uuid'
        seen = set()
        for key in ExtraMetadata.objects.filter(blob=self).values_list('key', flat=True):
            if key not in seen:
                yield key
            seen.add(key)
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
        for key in ExtraMetadata.objects.filter(blob=self).filter(second_value=None).values_list('key', flat=True):
            if key not in seen:
                yield key, ExtraMetadata.objects.filter(blob=self, key=key).filter(second_value=None).values_list('value', flat=True)
            seen.add(key)
    #
    def htmlitems(self):
        return coldoc_utils.metadata_html_items(self, self.coldoc.nickname)
    #
    def M_author(self):
        for j in ExtraMetadata.objects.filter(blob=self, key='M_author').values_list('value', flat=True):
            j = j.strip()
            if j and j[0] == '{': j=j[1:]
            if j and j[-1] == '}': j=j[:-1]
            #if ',' in j
            if j:
                yield j
    #
    def __str__(self):
        return 'DMetadata %s/%s (%d)' % (self.coldoc.nickname, self.uuid, self.id)


class ExtraMetadata(models.Model):
    blob = models.ForeignKey(DMetadata, on_delete=models.CASCADE, db_index = True)
    key = models.SlugField(max_length=80, db_index = True)
    value = models.CharField(max_length=120, db_index = True, blank=True)
    second_value = models.CharField(max_length=250, blank=True, null=True)


def uuid_replaced_by(coldoc, UUID):
    " returns list of blobs in `coldoc` that replace `UUID` "
    L =  ExtraMetadata.objects.filter(key = 'M_replaces').filter( advanced_query(value__contains = UUID )).all()
    if not L:
        return []
    L = [r  for r in L if r.blob.coldoc == coldoc]
    R = []
    for r in L:
        v = r.value
        v = re.split(',|;|/|\n|\t| ',v)
        v = [ a.rstrip('} \n').lstrip('\n {') for a in v ]
        if UUID in v:
            R.append(r.blob)
    return R
