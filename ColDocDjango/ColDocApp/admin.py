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

_inlines_ = []

if settings.USE_WALLET:
    from django_pursed.wallet.models import Wallet, Transaction
    class InlineWallet(admin.TabularInline):
        model = Wallet
        extra = 0
    #class InlineTransaction(admin.TabularInline):
    #    model = Transaction
    _inlines_ += [ InlineWallet, ]


from guardian.models import UserObjectPermission

class InlineUserObjectPermission(admin.TabularInline):
    model = UserObjectPermission
    extra = 0

_inlines_ += [  InlineUserObjectPermission ]


if settings.USE_ALLAUTH:
    from allauth.socialaccount.models import SocialAccount, EmailAddress
    #
    class InlineEmailAddress(admin.TabularInline):
        model = EmailAddress
    #
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
    _inlines_ += [ InlineSocialAccountAdmin,  InlineEmailAddress,  ]


class ColDocUserAdmin(UserAdmin):
    model = ColDocUser
    inlines = _inlines_

admin.site.register(ColDocUser, ColDocUserAdmin)
