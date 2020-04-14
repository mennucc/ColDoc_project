from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group


permissions_for_coldoc = ('view_metadata','change_metadata','add_blob','delete_blob')
permissions_for_blob = ('commit','view_metadata','change_metadata',
                        'view_blob','change_blob')
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
