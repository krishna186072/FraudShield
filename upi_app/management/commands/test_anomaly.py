import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from upi_app.models import UserProfile, Transaction
from upi_app.views import analyze_risk

class Command(BaseCommand):
    help = 'Simulates transactions to test the Anomaly Detection System'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting Anomaly Detection Simulation..."))

        # 1. Setup Test User
        username = "test_ai_user"
        email = "test_ai@example.com"
        
        # Cleanup old run
        if User.objects.filter(username=username).exists():
            User.objects.filter(username=username).delete()
            self.stdout.write("Cleaned up previous test user.")

        user = User.objects.create_user(username=username, email=email, password="password123")
        UserProfile.objects.create(
            user=user,
            upi_id="test_ai@upi",
            balance=100000.00,
            location="Mumbai"
        )
        self.stdout.write(self.style.SUCCESS(f"Created User: {username}"))

        # 2. Generate Training History (Normal Behavior)
        # Pattern: Small amounts (100-500), Mumbai (19.07, 72.87), Day time
        start_time = timezone.now() - timedelta(days=60)
        
        self.stdout.write("Generating 50 'Normal' past transactions to train the AI...")
        
        mumbai_lat, mumbai_lon = 19.0760, 72.8777
        
        for i in range(50):
            # Random time in last 60 days
            txn_time = start_time + timedelta(days=i, hours=random.randint(9, 21)) # 9 AM to 9 PM
            
            amount = Decimal(random.randint(100, 500))
            
            # Create Transaction directly (bypassing AI for history creation)
            Transaction.objects.create(
                sender=user,
                receiver_upi_id="merchant@upi",
                amount=amount,
                timestamp=txn_time,
                status='SUCCESS',
                location_lat=mumbai_lat + random.uniform(-0.01, 0.01), # Slight variance
                location_lon=mumbai_lon + random.uniform(-0.01, 0.01),
                device_id="TestDevice_Normal"
            )
            
        self.stdout.write(self.style.SUCCESS("History Generated. AI should now know 'Normal' pattern."))

        # 3. Runs Tests
        
        # Test A: Normal Transaction
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Test Case 1: Normal Transaction ---"))
        self.run_test(user, amount=250.00, lat=mumbai_lat, lon=mumbai_lon, city="Mumbai", label="Normal")

        # Test B: Slightly Suspicious (Medium Amount, Nearby City)
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Test Case 2: Suspicious (Medium Amount + Nearby City) ---"))
        # Pune Coords: 18.5204, 73.8567 (Near Mumbai). Amount 800 (slight spike)
        self.run_test(user, amount=800.00, lat=18.5204, lon=73.8567, city="Pune", label="Suspicious")

        # Test C: Extreme Anomaly (Huge Amount, Far Away, Midnight)
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Test Case 3: Extreme Fraud (Huge Amount + Foreign IP) ---"))
        # New York Coords: 40.7128, -74.0060. Amount 50,000.
        self.run_test(user, amount=50000.00, lat=40.7128, lon=-74.0060, city="New York", label="Fraud")

    def run_test(self, user, amount, lat, lon, city, label):
        """
        Runs analyze_risk and prints result
        """
        # Call the view's logic function
        is_suspicious, score, status, debug_info = analyze_risk(
            user=user,
            amount=amount,
            city=city,
            receiver_upi_id="unknown@upi",
            current_lat=lat,
            current_lon=lon,
            current_ip="127.0.0.1"
        )
        
        print(f"Scenario: {label}")
        print(f"Input:    Amount: {amount}, City: {city}")
        print(f"Output:   Score: {score:.4f} | Status: {status}")
        print(f"Debug:    {debug_info}")
        
        if label == "Normal" and status == 'SUCCESS':
            self.stdout.write(self.style.SUCCESS("PASS: Correctly identified as Normal."))
        elif label == "Suspicious" and status == 'PENDING_VERIFICATION':
            self.stdout.write(self.style.SUCCESS("PASS: Correctly triggered Verification."))
        elif label == "Fraud" and status == 'BLOCKED':
            self.stdout.write(self.style.SUCCESS("PASS: Correctly BLOCKED."))
        else:
            self.stdout.write(self.style.ERROR(f"FAIL: Unexpected status for {label} scenario."))
