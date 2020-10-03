from django.contrib import admin

# Register your models here.

# https://docs.djangoproject.com/en/3.0/ref/contrib/admin/

from .models import DMetadata, ExtraMetadata

class DMetadataAdmin(admin.ModelAdmin):
    readonly_fields = ('uuid',)


admin.site.register(DMetadata,DMetadataAdmin)


class ExtraMetadataAdmin(admin.ModelAdmin):
    pass

admin.site.register(ExtraMetadata, ExtraMetadataAdmin)
