from django.core.management.base import BaseCommand
from api.models import User

class Command(BaseCommand):
    help = 'Create default admin user if not exists'

    def handle(self, *args, **options):
        # Admin Details from User Request
        EC = "JC0033"
        FN = "Dhinakaran Sekar"
        RL = "admin"
        PW = "Admin@123"
        EM = "dhinakaran.s@jubilantenterprises.in"

        user, created = User.objects.get_or_create(
            employee_code=EC,
            defaults={
                'full_name': FN,
                'email': EM,
                'role': RL,
                'is_active': True,
                'is_initial_password': False, # Exempt auto-created admin from mandatory change
            }
        )

        if created:
            user.set_password(PW)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ Admin user {EC} created successfully."))
        else:
            # Update password even if exists, to ensure it matches the user's requested state
            user.set_password(PW)
            user.full_name = FN
            user.email = EM
            user.role = RL
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"🔄 Admin user {EC} already exists. Details synchronized."))
