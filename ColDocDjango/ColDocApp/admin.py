from django.contrib import admin
from django.conf import settings
from .models import DColDoc
from ColDocDjango.UUID.models import UUID_Tree_Edge

class UUID_Tree_Edge_Admin(admin.TabularInline):
    model = UUID_Tree_Edge
    readonly_fields = ('coldoc','parent','child','child_ordering')

class DColDocAdmin(admin.ModelAdmin):
    model = DColDoc
    inlines = [
        UUID_Tree_Edge_Admin,
    ]    
    readonly_fields = ('root_uuid',)

admin.site.register(DColDoc,DColDocAdmin)

# TODO maybe this is not the best place for this action
from django.contrib.auth.admin import UserAdmin
from ColDocDjango.users import ColDocUser

if settings.USE_ALLAUTH:
    from allauth.socialaccount.models import SocialAccount
    try:
        #https://github.com/pennersr/django-allauth/issues/2688
        from allauth.socialaccount.admin  import InlineSocialAccountAdmin
    except:
        class InlineSocialAccountAdmin(admin.TabularInline):
            model = SocialAccount
            search_fields = []
            raw_id_fields = ('user',)
            list_display = ('user', 'uid', 'provider')
            list_filter = ('provider',)
            def get_search_fields(self, request):
                base_fields = get_adapter().get_user_search_fields()
                return list(map(lambda a: 'user__' + a, base_fields))
    #
    class ColDocUserAdmin(UserAdmin):
        model = ColDocUser
        inlines = [
            InlineSocialAccountAdmin,
        ]
    admin.site.register(ColDocUser, ColDocUserAdmin)
else:
    admin.site.register(ColDocUser, UserAdmin)
