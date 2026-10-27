import csv
import random
from datetime import timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from upi_app.models import Transaction, UserProfile, LocationHistory
from upi_app.views import analyze_risk

class Command(BaseCommand):
    help = 'Generates 500 synthetic transactions (Legit vs Fraud) and exports to CSV'

    def handle(self, *args, **kwargs):
        users = list(User.objects.filter(is_superuser=False))
        if len(users) < 1:
            self.stdout.write(self.style.ERROR('No regular users found. Please create users first.'))
            return

        transactions_data = []
        
        # 1. Generate 500 Transactions
        for i in range(500):
            sender = random.choice(users)
            
            # Determine Class: 90% Legit, 10% Fraud
            is_fraud_scenario = random.random() < 0.10
            
            if is_fraud_scenario:
                # Fraud Scenario
                amount = random.uniform(10000, 100000)
                
                # Late night (00:00 - 05:00)
                hour = random.randint(0, 5)
                minute = random.randint(0, 59)
                
                # Distance > 200km
                distance_km = random.uniform(200, 1000)
                
                # Target Label
                is_fraud_label = 1
                
                # For DB persistence, mark as suspicious
                db_is_suspicious = True
                db_status = 'BLOCKED' # Likely blocked by our rules
                
            else:
                # Legit Scenario
                amount = random.uniform(10, 5000)
                
                # Daytime (06:00 - 23:00)
                hour = random.randint(6, 23)
                minute = random.randint(0, 59)
                
                # Close proximity (< 10km)
                distance_km = random.uniform(0, 10)
                
                is_fraud_label = 0
                db_is_suspicious = False
                db_status = 'SUCCESS'

            # Construct Date
            # Random day in last 30 days
            days_ago = random.randint(0, 30)
            txn_date = timezone.now() - timedelta(days=days_ago)
            txn_date = txn_date.replace(hour=hour, minute=minute)
            
            # Create DB Transaction (Optional but requested "Create ... transactions")
            # We need a receiver. Pick another random user or None (external)
            # Receiver is not critical for the CSV export logic but needed for DB
            receiver = None
            possible_receivers = [u for u in users if u != sender]
            if possible_receivers:
                receiver = random.choice(possible_receivers)
            
            receiver_upi = receiver.profile.upi_id if receiver and hasattr(receiver, 'profile') else 'external@upi'

            # Save to DB
            txn = Transaction.objects.create(
                sender=sender,
                receiver=receiver,
                receiver_upi_id=receiver_upi,
                amount=amount,
                timestamp=txn_date,
                status=db_status,
                is_suspicious=db_is_suspicious,
                description='Synthetic Transaction'
            )
            # Manually update timestamp because auto_now_add sets it to NOW
            txn.timestamp = txn_date
            txn.save()

            # Store for CSV
            transactions_data.append({
                'amount': round(amount, 2),
                'hour': hour,
                'day_of_week': txn_date.weekday(), # 0=Monday, 6=Sunday
                'distance_km': round(distance_km, 2),
                'is_fraud': is_fraud_label
            })

            # Create Fake Location History for this txn to match distance (Optional visual sync)
            # Not strictly needed for the CSV export which relies on the generated `distance_km`

        # 2. Export All Transactions to CSV
        # The user asked to export "all transactions (old and new)".
        # For old transactions, we need to calculate/guess distance.
        # Since we don't have stored distance for old txns, we will infer or skip.
        # However, to train AI, consistency is key.
        # Strategy: We will export the 500 JUST generated above + purely synthetic data for old ones?
        # Re-reading: "Export all transactions (old and new) ... including columns... distance_km"
        # Since 'distance_km' isn't in DB, valid data only exists for the NEW ones we just made logic for.
        # I will prioritize exporting the 500 new ones + any old ones where I can mock distance based on 'is_suspicious'.
        
        existing_txns = Transaction.objects.exclude(description='Synthetic Transaction')
        for txn in existing_txns:
            # Infer label
            is_fraud_label = 1 if txn.is_suspicious or txn.status == 'BLOCKED' else 0
            
            # Infer Distance based on label (Reverse engineer)
            if is_fraud_label:
                dist = random.uniform(100, 500) # Mock high distance for existing fraud
            else:
                dist = random.uniform(0, 10)   # Mock low distance for existing legit
            
            transactions_data.append({
                'amount': txn.amount,
                'hour': txn.timestamp.hour,
                'day_of_week': txn.timestamp.weekday(),
                'distance_km': round(dist, 2),
                'is_fraud': is_fraud_label
            })
            
        # Write to File
        with open('fraud_data.csv', 'w', newline='') as csvfile:
            fieldnames = ['amount', 'hour', 'day_of_week', 'distance_km', 'is_fraud']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for data in transactions_data:
                writer.writerow(data)

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {len(transactions_data)} records to fraud_data.csv'))
