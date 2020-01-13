from django.contrib import admin

# Register your models here.


from .models import BlobMetadata

admin.site.register(BlobMetadata)
