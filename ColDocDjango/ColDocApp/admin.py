from django.contrib import admin
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
admin.site.register(ColDocUser, UserAdmin)
