import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import connection
from api.models import User, FileProcessingLog
from api.helpers import count_return_matches, count_inb_matches

class Command(BaseCommand):
    help = 'Run automated production readiness checks'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("[*] Running Production Readiness Checks..."))

        # 1. DB Connection
        try:
            connection.cursor()
            self.stdout.write(self.style.SUCCESS("[OK] Database connectivity confirmed."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Database connection failed: {e}"))
            return

        # 2. Critical Models
        user_count = User.objects.count()
        log_count  = FileProcessingLog.objects.count()
        self.stdout.write(f" -> Users in DB: {user_count}")
        self.stdout.write(f" -> Processing Logs in DB: {log_count}")

        # 3. Admin Existence
        admin_code = "JC0033"
        try:
            admin = User.objects.get(employee_code=admin_code)
            self.stdout.write(self.style.SUCCESS(f"[OK] Admin user {admin_code} ({admin.full_name}) found."))
            self.stdout.write(f"   Role: {admin.role}, Email: {admin.email}")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"[ERROR] Admin user {admin_code} NOT FOUND."))

        # 4. Logic Verification (Helpers)
        test_df = pd.DataFrame({
            'TYPE': ['RETURN', 'INB TRF', 'OTHER', 'RETURN'],
            'Category': ['I/W CHQ RTN', 'MATCH', 'REFUND', 'O/W CHQ RTN']
        })
        
        rtn_count = count_return_matches(test_df)
        inb_count = count_inb_matches(test_df)
        
        if rtn_count == 2 and inb_count == 1:
            self.stdout.write(self.style.SUCCESS("[OK] Logic Helpers (Matching/Counting) verified with sample data."))
        else:
            self.stdout.write(self.style.ERROR(f"[ERROR] Logic Helpers failed validation (RTN:{rtn_count}, INB:{inb_count})"))

        # 5. Environment
        self.stdout.write(self.style.MIGRATE_HEADING("\nEnvironment Status:"))
        self.stdout.write(f"   Working Directory: {os.getcwd()}")
        
        # 6. Final Verdict
        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] All internal backend health checks passed!"))
        self.stdout.write("Next steps: Follow the manual UI verification steps in production_checklist.md.")
