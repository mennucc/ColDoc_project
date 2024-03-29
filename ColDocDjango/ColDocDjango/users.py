import sys
import logging
logger = logging.getLogger(__name__)

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group


permissions_for_coldoc_extra = ['add_blob','delete_blob','commit']
permissions_for_coldoc = permissions_for_coldoc_extra + ['view_dcoldoc','change_dcoldoc']

# 'view_metadata','change_metadata', are standard, added by Django
permissions_for_blob_extra = ['view_view','view_log','view_blob','change_blob','download','commit']
permissions_for_blob = permissions_for_blob_extra + ['view_dmetadata','change_dmetadata']
groups_for_coldoc = ('editors','authors')

def name_of_permission_for_coldoc(coldoc,permission):
    assert permission in permissions_for_coldoc
    return permission+'_on_'+coldoc

def name_of_permission_for_blob(coldoc,permission):
    assert permission in permissions_for_blob
    return permission+'_on_blob_inside_'+coldoc

def name_of_group_for_coldoc(coldoc,group):
    assert group in groups_for_coldoc
    return 'coldoc_'+coldoc+'_group_'+group

def add_permissions_for_coldoc(nickname):
    # import here to avoid circular dependencies
    import ColDocApp.models as coldocapp_models
    import UUID.models as  blob_models
    # https://docs.djangoproject.com/en/3.0/topics/auth/default/
    P = {}
    for p in permissions_for_coldoc:
        content_type = ContentType.objects.get_for_model(coldocapp_models.DColDoc)
        n = name_of_permission_for_coldoc(nickname,p)
        try:
            permission = Permission.objects.get(codename = n)
        except Permission.DoesNotExist :
            permission = Permission.objects.create(codename = n,
                            name=' can '+p+' on ColDoc '+nickname,
                            content_type=content_type,) 
            permission.save()
        P[('c',p)] = permission
    for p in permissions_for_blob:
        content_type = ContentType.objects.get_for_model(blob_models.DMetadata)
        n = name_of_permission_for_blob(nickname,p)
        try:
            permission = Permission.objects.get(codename = n)
        except Permission.DoesNotExist :
            permission = Permission.objects.create(codename = n,
                            name=' can '+p+' for blobs in ColDoc '+nickname,
                            content_type=content_type,)
            permission.save()
        P[('b',p)] = permission
    for n_ in groups_for_coldoc:
        n = name_of_group_for_coldoc(nickname, n_)
        try:
            gr = Group.objects.get(name = n)
        except Group.DoesNotExist :
            gr = Group()
            gr.name = n
            gr.save()
        for l,p_ in P:
            p = P[(l,p_)]
            if (n_ == 'editors' and (l == 'c' or p_ in ('view_view', 'view_log'))) \
               or  (n_ == 'authors' and l == 'b'):
                logger.debug(" n %r l %r p_ %r p %r ", n, l, p_, p)
                gr.permissions.add(p)
        gr.save()

UUID_view_view = sys.intern('UUID.view_view')
UUID_view_blob = sys.intern('UUID.view_blob')
UUID_download  = sys.intern('UUID.download')

def user_has_perm_uuid_blob(username_, perm, blob):
    if blob.author.filter(username = username_).exists():
        #allow complete access to authors
        return True
    s = blob.access
    if s == 'open' and perm in (UUID_view_view, UUID_view_blob, UUID_download):
        return True
    elif s == 'public' and perm in (UUID_view_view,):
        return True
    return False


def user_has_perm(user, perm, coldoc, blob, object_):
    """ when calling this, make sure that `user` is not an instance of `ColDocUser` ; in case, user `super`.
    This is used only for authenticated users. For anonymous users, see
    ColDocDjango.users.ColDocAnonymousUser
    """
    if not user.is_active:
        return False
    #
    DMetadata = None
    if blob is not None:
        from UUID.models import DMetadata
        assert isinstance(blob, DMetadata)
    #
    assert not isinstance(user,ColDocAnonymousUser)
    assert not isinstance(user,ColDocUser)
    #assert blob is None or 'UUID.models.DMetadata' in str(type(blob)) # unfortunately isinstance(obj, DMetadata) will break because of circular imports
    perm_uuid   = perm.startswith('UUID.')
    perm_coldoc = perm.startswith('ColDocApp.')
    #
    if object_ is not None:
        # object_ has precedence
        if blob is not None and blob != object_ and perm_uuid :
            logger.warning('Evaluating user %s  permission %r on obj %r and not on blob %r  ', user.username, perm, object_, blob)
        if user.has_perm(perm, object_):
            # django-guardian will check for specific permissions for this object
            logger.debug('Indeed %r has permission %r, object %r ', user.username, perm, object_)
            return True
        obj = object_
    else:
        if blob is not None and  perm_uuid  and user.has_perm(perm, blob):
            # django-guardian will check for specific permissions for this blob
            logger.debug('Indeed %r has permission %r, blob %r ', user.username, perm, blob)
            return True
        obj = blob
    # django-guardian does not check "global permission"
    if user.has_perm(perm):
        if obj is not None:
            logger.debug("Granting %r to %s, false on %r but true globally", perm, user.username, obj)
        # takes care of superuser
        return True
    #
    if coldoc is None:
        if perm_coldoc or perm_uuid:
            logger.warning("Should not reach this point")
        return False
    #
    if perm_uuid and perm[5:] in permissions_for_blob:
        # we can assume that when object_ is None, then obj==blob , that was a Dmetadata instance or None
        if object_ is not None and 'UUID.models.DMetadata' not in str(type(obj)): 
            # the code following checks permissions for blobs only
            logger.warning('Bail out %r  permission %r since obj %r is not DMetadata  ', user.username, perm, obj)
            return False
        n = name_of_permission_for_blob(coldoc.nickname, perm[5:])
        if user.has_perm('UUID.'+n, obj):
            return True
        # django-guardian does not check "global permission"
        if obj is not None and user.has_perm('UUID.'+n):
            logger.debug("Granting %r to %s, false on %r but true on coldoc %r", perm, user.username, obj, coldoc)
            return True
        #
        if obj is not None:
            return user_has_perm_uuid_blob(user.username, perm, obj)
        return False
    if perm_coldoc and perm[10:] in permissions_for_coldoc:
        n = 'ColDocApp.' + name_of_permission_for_coldoc(coldoc.nickname, perm[10:])
        # we already checked user.has_perm(perm, object_) when object_ is not None
        if user.has_perm(n):
            ##logger.debug('Indeed %r has permission %r, coldoc %r ,blob, %r, obj %r ',user.username,n,coldoc,blob,obj)
            return True
        if perm == 'ColDocApp.add_blob' and coldoc.author_can_add_blob and \
           blob is not None and blob.author.filter(username=user.username).exists():
            return True
    return False
    

#####################################
# https://docs.djangoproject.com/en/3.0/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project

#from django.conf import settings

from django.contrib.auth.models import AbstractUser


class BaseColDocUser():
    def associate_coldoc_blob_for_has_perm(self, coldoc, blob):
        from ColDocApp.models import DColDoc
        from UUID.models import DMetadata
        if coldoc is not None and not isinstance(coldoc, DColDoc):
            logger.error(" type %r instead of DColDoc",coldoc)
            coldoc = None
        self._coldoc = coldoc
        from UUID.models import DMetadata
        if blob is not None and not isinstance(blob, DMetadata):
            logger.error(" type %r instead of DMetadata",blob)
            blob = None
        self._blob = blob

    #
    @property
    def is_editor(self):
        return False
    #
    @property
    def is_author(self):
        return False


class ColDocUser(AbstractUser, BaseColDocUser):
    class Meta:
        app_label = 'ColDocApp'
    def __init__(self, *v, **k):
        # will be an instance of DColDoc
        self._coldoc = None
        # will be an instance of DMetadata
        self._blob = None
        super(AbstractUser,self).__init__(*v, **k)
    #
    @property
    def is_editor(self):
        if self._coldoc is None:
            return False
        n = name_of_group_for_coldoc(self._coldoc.nickname, 'editors')
        gr = Group.objects.get(name = n)
        return gr.user_set.filter(id=self.id).exists()
    #
    @property
    def pretty_user_name(self):
        if self.first_name or self.last_name:
            return '"' + self.last_name + ' , ' + self.first_name + '"'
        return self.username
    #
    @property
    def is_author(self):
        if self._blob is None:
            return False
        #from ColDocApp.models import DColDoc
        return self._blob.author.filter(username=self.username).exists()
    #
    def has_perm(self, perm, obj=None):
        if self._coldoc is None:
            return super(AbstractUser,self).has_perm(perm, obj)
        v = False
        try:
            v = user_has_perm(super(), perm, self._coldoc, self._blob, obj)
            logger.debug('check user %s perm "%s" coldoc "%s" blob "%s" obj %r -> %r',
                       self, perm, self._coldoc, self._blob, obj, v)
        except:
            logger.exception('failed check on permission, set to False ; user %s perm "%s" coldoc "%s" blob "%s" obj %r',
                             self, perm, self._coldoc, self._blob, obj)
        return v
    # https://docs.djangoproject.com/en/dev/ref/models/instances/#django.db.models.Model.get_absolute_url
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('user') + ('?nr=%s' % (self.id,))
    #
    def __str__(self):
        return self.pretty_user_name


# https://github.com/bugov/django-custom-anonymous

from django.contrib.auth.models import AnonymousUser as DjangoAnonymousUser

class ColDocAnonymousUser(DjangoAnonymousUser, BaseColDocUser):
    def __init__(self, request, *v, **k):
        self._coldoc = None
        self._blob = None
        super().__init__(*v, **k)
    def has_perm(self, perm, obj=None):
        if  self._coldoc is None :
            return super().has_perm(perm, obj)
        if perm in  (UUID_view_view,):
            if not self._coldoc.anonymous_can_view:
                return False
            blob = obj if ( obj is not None and hasattr(obj, 'access') ) else self._blob
            if blob is not None:
                return (blob.access in ('open','public'))
        return super().has_perm(perm, obj)

