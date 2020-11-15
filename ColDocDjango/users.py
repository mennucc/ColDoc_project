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
    import ColDocDjango.ColDocApp.models as coldocapp_models
    import ColDocDjango.UUID.models as  blob_models
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
    for n in groups_for_coldoc:
        n = name_of_group_for_coldoc(nickname,n)
        try:
            gr = Group.objects.get(name = n)
        except Group.DoesNotExist :
            gr = Group()
            gr.name = n
            gr.save()
        for l,p in P:
            p = P[(l,p)]
            if n == 'editors' or l == 'b':
                gr.permissions.add(p)
        gr.save()

def user_has_perm(user, perm, coldoc, blob, object_):
    """ when calling this, make sure that `user` is not an instance of `ColDocUser` ; in case, user `super`.
    This is used only for authenticated users. For anonymous users, see
    ColDocDjango.users.ColDocAnonymousUser
    """
    if not user.is_active:
        return False
    if object_ is None and perm.startswith('UUID.') and blob is not None:
        # django-guardian will check for specific permissions for this blob
        obj = blob
    else:
        obj = object_
    if user.has_perm(perm, obj):
        ##logger.debug('Indeed %r has permission %r, coldoc %r ,blob, %r, obj %r ',user.username,perm,coldoc,blob,obj)
        # takes care of superuser
        return True
    #
    if object_ is not None and object_ != blob:
        # the code following checks permissions for blobs only
        logger.debug('Bail out %r  permission %r since blob %r != obj %r ',user.username,perm,blob,object_)
        return False
    #
    if coldoc is None:
        logger.warning("Should not reach this point")
        return False
    if perm.startswith('UUID.') and perm[5:] in permissions_for_blob:
        n = name_of_permission_for_blob(coldoc.nickname, perm[5:])
        if user.has_perm('UUID.'+n, obj):
            return True
        if blob is not None: 
            if blob.author.filter(username=user.username).exists():
                #allow complete access to authors
                return True
            s = blob.access
            if s == 'open' and perm in ('UUID.view_view', 'UUID.view_blob'):
                return True
            elif s == 'public' and perm in ('UUID.view_view',):
                return True
        # editor access to the whole document and to logs
        if  perm in ('UUID.view_view', 'UUID.view_log' ) and \
            coldoc.editor.filter(username=user.username).exists() :
            return True
        return False
    if perm.startswith('ColDocApp.') and perm[10:] in permissions_for_coldoc:
        #allow complete access to editors
        if coldoc.editor.filter(username=user.username).exists():
            return True
        n = 'ColDocApp.' + name_of_permission_for_coldoc(coldoc.nickname, perm[10:])
        if user.has_perm(n, obj):
            ##logger.debug('Indeed %r has permission %r, coldoc %r ,blob, %r, obj %r ',user.username,n,coldoc,blob,obj)
            return True
        if perm == 'ColDocApp.add_blob' and coldoc.author_can_add_blob and \
           blob is not None and blob.author.filter(username=user.username).exists():
            return True
    return False
    

#####################################
# https://docs.djangoproject.com/en/3.0/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project

from django.conf import settings

from django.contrib.auth.models import AbstractUser


class BaseColDocUser():
    def associate_coldoc_blob_for_has_perm(self, coldoc, blob):
        from ColDocDjango.ColDocApp.models import DColDoc
        from ColDocDjango.UUID.models import DMetadata
        if coldoc is not None and not isinstance(coldoc, DColDoc):
            logger.error(" type %r instead of DColDoc",coldoc)
            coldoc = None
        self._coldoc = coldoc
        from ColDocDjango.UUID.models import DMetadata
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
    #
    @property
    def pretty_user_name(self):
        if self.first_name or self.last_name:
            return self.last_name + ' , ' + self.first_name
        return self.username
    


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
        from ColDocDjango.ColDocApp.models import DColDoc
        return self._coldoc.editor.filter(username=self.username).exists()
    #
    @property
    def is_author(self):
        if self._blob is None:
            return False
        from ColDocDjango.ColDocApp.models import DColDoc
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
            logger.exception('failed check on permission, set to False')
        return v


# https://github.com/bugov/django-custom-anonymous

from django.contrib.auth.models import AnonymousUser as DjangoAnonymousUser

class ColDocAnonymousUser(DjangoAnonymousUser, BaseColDocUser):
    def __init__(self, request, *v, **k):
        self._coldoc = None
        self._blob = None
        super().__init__(*v, **k)
    def has_perm(self, perm, obj=None):
        if self._coldoc is None or self._blob is None:
            return super().has_perm(perm, obj)
        if perm in  ('UUID.view_view',):
            if not self._coldoc.anonymous_can_view:
                return False
            r = (self._blob.access in ('open','public'))
            return r
        return super().has_perm(perm, obj)

