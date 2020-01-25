from django.urls import path

from . import views

app_name = 'ColDoc'
urlpatterns = [
    path('<str:NICK>', views.index, name='index'),
    path('<str:NICK>/', views.index),
    path('<str:NICK>/index.html', views.index),
]
