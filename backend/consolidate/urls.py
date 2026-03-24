from django.urls import path
from . import views

urlpatterns = [
    path('', views.ConsolidateView.as_view(), name='consolidate'),
]
