from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from upi_app.models import UserProfile, Transaction
from decimal import Decimal
import random
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Seeds the database with users and transactions for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')
        
        # 1. Create Users
        users = []
        for i in range(5):
            username = f'user{i+1}'
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password='password123')
                # Create Profile
                UserProfile.objects.create(
                    user=user,
                    upi_id=f'{username}@upi',
                    phone_number=f'98765432{i}0',
                    balance=Decimal(random.uniform(5000, 50000)),
                    total_spent=0,
                    is_verified=True
                )
                users.append(user)
                self.stdout.write(f'Created user: {username}')
            else:
                users.append(User.objects.get(username=username))

        # 2. Generate Transactions
        for _ in range(50):
            sender = random.choice(users)
            receiver = random.choice([u for u in users if u != sender])
            
            amount = Decimal(random.uniform(100, 20000))
            is_night = random.choice([True, False])
            
            # Simulate Risk
            status = 'SUCCESS'
            is_suspicious = False
            fraud_score = 0.0
            
            # Logic similar to analyze_risk
            if amount > 10000:
                is_suspicious = True
                fraud_score += 50
                status = 'BLOCKED'
            
            if is_night: # Simulate night time logically (just for attribute)
                 time_offset = random.randint(0, 5) # 12 AM to 5 AM
                 fraud_score += 30
                 if fraud_score > 80:
                     status = 'BLOCKED'
            else:
                 time_offset = random.randint(6, 23)

            # Create Timestamp
            days_ago = random.randint(0, 30)
            txn_time = timezone.now() - timedelta(days=days_ago)
            # Adjust hour roughly (not perfect in Django timezone aware, but good enough for data)
            txn_time = txn_time.replace(hour=time_offset)

            Transaction.objects.create(
                sender=sender,
                receiver=receiver,
                receiver_upi_id=receiver.profile.upi_id,
                amount=amount,
                timestamp=txn_time,
                description=f'Test payment {random.randint(1000,9999)}',
                status=status,
                fraud_score=fraud_score,
                is_suspicious=is_suspicious,
                device_id=f'Device-{random.randint(1,5)}'
            )
            
            if status == 'SUCCESS':
                sender.profile.balance -= amount
                sender.profile.total_spent += amount
                sender.profile.save()
                receiver.profile.balance += amount
                receiver.profile.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded 50 transactions!'))
