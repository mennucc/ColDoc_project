from django.contrib import admin

# Register your models here.

# https://docs.djangoproject.com/en/3.0/ref/contrib/admin/

from .models import DMetadata, ExtraMetadata


class ExtraMetadataAdmin(admin.TabularInline):
    model = ExtraMetadata

class DMetadataAdmin(admin.ModelAdmin):
    model = DMetadata
    inlines = [
        ExtraMetadataAdmin,
    ]    
    readonly_fields = ('uuid','coldoc',)

admin.site.register(DMetadata,DMetadataAdmin)

