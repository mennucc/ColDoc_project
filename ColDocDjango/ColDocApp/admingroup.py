# https://stackoverflow.com/a/57913083/5058564
from django import forms
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()

class GroupAdminForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(), 
        required=False,
        widget=FilteredSelectMultiple(
            verbose_name=_('Users'),
            is_stacked=False
        )
    )

    class Meta:
        model = Group
        exclude = []

    def __init__(self, *args, **kwargs):
        super(GroupAdminForm, self).__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields['users'].initial = self.instance.user_set.all()

class GroupAdmin(admin.ModelAdmin):
    form = GroupAdminForm

    def save_model(self, request, obj, form, change):
        super(GroupAdmin, self).save_model(request, obj, form, change)
        if 'users' in form.cleaned_data:
            form.instance.user_set.set(form.cleaned_data['users'])


admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)
