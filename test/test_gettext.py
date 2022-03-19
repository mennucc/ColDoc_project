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
from django.utils.text import format_lazy

print('here a translation')
a = gettext_lazy('help')
print('and it is lazy ',type(a))

m = ' ... %s ...' % a
print('and it is NOT lazy ',type(m))

m = format_lazy('{}\n', a)
print('format_lazy is lazy ',type(m))

print('fine')
a = gettext_lazy('help') + 'here'
print('but now it is not lazy it is string ',type(a))


print('crashes in django 3')
a = 'here' + gettext_lazy('help')
print('and it is NOT lazy ',type(a))


print('crashes in django 3')
a = gettext_lazy('here') + gettext_lazy('help')
print('and it is NOT lazy',type(a))

