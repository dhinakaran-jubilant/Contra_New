from django.urls import path
from working.views import WorkingView

urlpatterns = [
    path('', WorkingView.as_view(), name='working'),
]
