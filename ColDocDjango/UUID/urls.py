from django.urls import path

from . import views

urlpatterns = [
    #path('', views.index, name='index'),
    # ex: /UUID/5/
    path('<str:UUID>/pdf', views.pdf, name='pdf'),
    path('<str:UUID>', views.index, name='index'),
    path('<str:UUID>/', views.index, name='index'),
    path('<str:UUID>/index.html', views.index, name='index'),
]
