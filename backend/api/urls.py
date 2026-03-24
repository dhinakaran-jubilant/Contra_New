from django.urls import path
from api import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('users/', views.get_users, name='get_users'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/delete/<str:employee_code>/', views.delete_user, name='delete_user'),
    path('users/update/<str:employee_code>/', views.update_user, name='update_user'),
    path('users/initial-setup/', views.update_initial_setup, name='update_initial_setup'),
    path('forgot-password/request/', views.forgot_password_request, name='forgot_password_request'),
    path('forgot-password/reset/', views.forgot_password_reset, name='forgot_password_reset'),
    path('download-file/', views.download_file, name='download_file'),
    path('stats/', views.get_stats, name='get_stats'),
    path('get_processing_logs/', views.get_processing_logs, name='get_processing_logs'),
]
