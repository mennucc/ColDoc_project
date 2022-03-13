#!/usr/bin/env python3



import os, django, sys

b = os.path.abspath(os.path.dirname(sys.argv[0]))
p = os.path.dirname(b)
c = os.path.join(p,'ColDocDjango')
sys.path.insert(0,c)
os.chdir(c)
#print(os.getcwd(c))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ColDocDjango.settings')
django.setup()

from django.utils.translation import gettext, gettext_lazy, gettext_noop, activate

print('fine')
a = gettext_lazy('help')
print('and it is lazy ',type(a))


print('fine')
a = gettext_lazy('help') + 'here'
print('but now it is not lazy it is string ',type(a))


print('crashes in django 3')
a = 'here' + gettext_lazy('help')
print('and it is ',type(a))


print('crashes in django 3')
a = gettext_lazy('here') + gettext_lazy('help')
print('and it is ',type(a))

