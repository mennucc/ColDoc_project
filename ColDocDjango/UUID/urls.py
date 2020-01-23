from django.urls import path

from . import views

urlpatterns = [
    path('<str:NICK>/<str:UUID>/pdf', views.pdf, name='pdf'),
    #
    path('<str:NICK>/<str:UUID>/html/<path:subpath>', views.html, name='html'),
    path('<str:NICK>/<str:UUID>/html/', views.html, name='html'),
    #
    path('<str:NICK>/<str:UUID>', views.index, name='index'),
    path('<str:NICK>/<str:UUID>/', views.index, name='index'),
    path('<str:NICK>/<str:UUID>/index.html', views.index, name='index'),
]
