from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class User(models.Model):

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        USER = 'user', 'User'
        VIEWER = 'viewer', 'Viewer'

    employee_code = models.CharField(max_length=50, unique=True)
    full_name     = models.CharField(max_length=150)
    email         = models.EmailField(unique=True)
    role          = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_active     = models.BooleanField(default=True)
    is_deleted    = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=256)
    is_initial_password = models.BooleanField(default=True)
 
    # Security Questions
    security_q1   = models.CharField(max_length=255, null=True, blank=True)
    security_a1   = models.CharField(max_length=255, null=True, blank=True)
    security_q2   = models.CharField(max_length=255, null=True, blank=True)
    security_a2   = models.CharField(max_length=255, null=True, blank=True)
    security_q3   = models.CharField(max_length=255, null=True, blank=True)
    security_a3   = models.CharField(max_length=255, null=True, blank=True)
 
    created_at    = models.DateTimeField(auto_now_add=True)
    last_login    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users'
        ordering = ['employee_code']

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def verify_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

    def __str__(self):
        return f"{self.employee_code} — {self.full_name}"


class FileProcessingLog(models.Model):
    user_name = models.CharField(max_length=150)
    file_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    processed_at = models.DateTimeField(default=timezone.now)
    total_entries = models.IntegerField(default=0)
    
    # Textual counts in format: [inb_trf: 10, sis_con: 15, ...]
    software_count = models.TextField(null=True, blank=True)
    final_count = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'file_processing_logs'
        ordering = ['-processed_at']

    def __str__(self):
        return f"{self.user_name} - {self.file_name} ({self.processed_at.strftime('%Y-%m-%d %H:%M')})"
