from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from upi_app.models import UserProfile
import random

class Command(BaseCommand):
    help = 'Seeds the database with specific users'

    def handle(self, *args, **kwargs):
        users_to_create = ['Akhil', 'krishna', 'karthik', 'john', 'hrishikesh']
        common_password = 'password123'
        common_pin = '123456'
        cities = ['Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai', 'Pune', 'Kolkata']

        # Delete existing non-superusers - REMOVED to preserve history
        # self.stdout.write('Deleting existing users...')
        # User.objects.filter(is_superuser=False).delete()

        for name in users_to_create:
            username = name.lower()
            email = f"{username}@example.com"
            
            # Get or Create User
            user, created = User.objects.get_or_create(username=username, defaults={
                'email': email,
                'password': common_password,
                'first_name': name.capitalize()
            })
            
            if created:
                user.set_password(common_password)
                user.save()
                self.stdout.write(f"Created new user: {name}")
            else:
                self.stdout.write(f"Found existing user: {name}")

            # Create Profile
            location = random.choice(cities)
            upi_id = f"{username}@upi"
            
            profile, profile_created = UserProfile.objects.get_or_create(user=user)
            
            # Only set specific fields if they are missing or if we want to force an update (like balance)
            # We will force update critical demo fields but PRESERVE the ID (so relationships stay)
            profile.upi_id = upi_id
            if not profile.location:
                profile.location = location
            if not profile.pin:
                profile.pin = common_pin
            
            # Ensure balance is correct for demo
            profile.balance = 100000.00
            
            profile.save()

            self.stdout.write(self.style.SUCCESS(f'Updated/Verified user: {name} ({upi_id})'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded/updated users without data loss.'))
