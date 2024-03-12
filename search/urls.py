from django.urls import path
from . import views

urlpatterns = [
  path('', views.index, name='show_main'),  
  path('result/', views.show_result, name='show_result'),
  path('filtered/', views.show_filtered, name='show_filtered'),
  path('detail/', views.detail, name='detail'),
]