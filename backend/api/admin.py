from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display  = ('employee_code', 'full_name', 'email', 'role', 'is_active', 'created_at')
    list_filter   = ('role', 'is_active')
    search_fields = ('employee_code', 'full_name', 'email')
    readonly_fields = ('created_at', 'last_login')

