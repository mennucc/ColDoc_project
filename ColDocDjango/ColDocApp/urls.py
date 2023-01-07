from django.urls import path

from . import views

app_name = 'ColDoc'
urlpatterns = [
    path('<str:NICK>', views.index, name='index'),
    path('<str:NICK>/', views.index),
    path('<str:NICK>/index.html', views.index),
    path('<str:NICK>/html/<path:subpath>', views.html, name='html'),
    path('<str:NICK>/html/', views.html, name='html'),
    path('<str:NICK>/pdf', views.pdf, name='pdf'),
    path('<str:NICK>/pdfframe', views.pdfframe, name='pdfframe'),
    path('<str:NICK>/search', views.search, name='search'),
    path('<str:NICK>/check_tree', views.check_tree, name='check_tree'),
    path('<str:NICK>/postcoldocedit', views.post_coldoc_edit, name='postcoldocedit'),
    path('<str:NICK>/latex', views.latex, name='latex'),
    path('<str:NICK>/reparse', views.reparse, name='reparse'),
]
