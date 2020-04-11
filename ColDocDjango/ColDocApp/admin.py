from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import DColDoc , ColDocUser

admin.site.register(DColDoc)

admin.site.register(ColDocUser, UserAdmin)
