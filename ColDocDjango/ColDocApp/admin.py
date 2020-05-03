from django.contrib import admin
from .models import DColDoc

admin.site.register(DColDoc)

# TODO maybe this is not the best place for this action
from django.contrib.auth.admin import UserAdmin
from ColDocDjango.users import ColDocUser
admin.site.register(ColDocUser, UserAdmin)
