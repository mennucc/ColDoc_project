from django.urls import path

from . import views

app_name = 'UUID'
urlpatterns = [
    path('<str:NICK>/<str:UUID>/pdf', views.pdf, name='pdf'),
    #
    path('<str:NICK>/<str:UUID>/html/<path:subpath>', views.html),
    path('<str:NICK>/<str:UUID>/html/', views.html, name='html'),
    #
    path('<str:NICK>/<str:UUID>/show/', views.show, name='show'),
    #
    path('<str:NICK>/<str:UUID>/log/', views.log, name='log'),
    #
    path('<str:NICK>/<str:UUID>/postedit/', views.postedit, name='postedit'),
    path('<str:NICK>/<str:UUID>/postupload/', views.postupload, name='postupload'),
    path('<str:NICK>/<str:UUID>/postmetadataedit/', views.postmetadataedit, name='postmetadataedit'),
    path('<str:NICK>/<str:UUID>/', views.index, name='index'),
    path('<str:NICK>/<str:UUID>/download', views.download, name='download'),
    path('<str:NICK>/<str:UUID>/md5/<path:FILE>', views.md5, name='md5'),
]
