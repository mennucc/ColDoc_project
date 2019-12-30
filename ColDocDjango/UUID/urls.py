from django.urls import path

from . import views

urlpatterns = [
    #path('', views.index, name='index'),
    # ex: /UUID/5/
    path('<str:UUID>/', views.index, name='index'),
]
