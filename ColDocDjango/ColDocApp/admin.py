from django.contrib import admin
from .models import DColDoc


class DColDocAdmin(admin.ModelAdmin):
    model = DColDoc
    readonly_fields = ('root_uuid',)

admin.site.register(DColDoc,DColDocAdmin)

# TODO maybe this is not the best place for this action
from django.contrib.auth.admin import UserAdmin
from ColDocDjango.users import ColDocUser
admin.site.register(ColDocUser, UserAdmin)
