from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group


permissions_for_coldoc = ('add_blob','delete_blob','commit')
# 'view_metadata','change_metadata', are standard, added by Django
permissions_for_blob_extra = ['view_view','view_blob','change_blob','download','commit']
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
        permission = Permission.objects.create(
            codename = name_of_permission_for_coldoc(nickname,p),
            name=' can '+p+' on ColDoc '+nickname,
            content_type=content_type,)
        permission.save()
        P[('c',p)] = permission
    for p in permissions_for_blob:
        content_type = ContentType.objects.get_for_model(blob_models.DMetadata)
        permission = Permission.objects.create(
            codename = name_of_permission_for_blob(nickname,p),
            name=' can '+p+' for blobs in ColDoc '+nickname,
            content_type=content_type,)
        permission.save()
        P[('b',p)] = permission
    for n in groups_for_coldoc:
        gr = Group()
        gr.name = name_of_group_for_coldoc(nickname,n)
        gr.save()
        for l,p in P:
            p = P[(l,p)]
            if n == 'editors' or l == 'b':
                gr.permissions.add(p)
        gr.save()

def user_has_perm(user, perm, coldoc, blob, obj):
    " when calling this, make sure that `user` is not an instance of `ColDocUser` ; in case, user `super`"
    if not user.is_active:
        return False
    if user.has_perm(perm, obj):
        # takes care of superuser
        return True
    if coldoc is None:
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
        return False
    if perm.startswith('ColDocApp.') and  \
       perm[len('ColDocApp.'):] in permissions_for_coldoc:
        n = name_of_permission_for_coldoc(coldoc.nickname, perm)
        if user.has_perm(n, obj):
            return True
    return False
    
