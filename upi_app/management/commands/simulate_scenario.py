from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from upi_app.models import UserProfile, Transaction, Feedback, LocationHistory
from decimal import Decimal
import time
from upi_app.views import analyze_risk

class Command(BaseCommand):
    help = 'Simulates transactions and bad actor reporting'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Simulation...")
        
        # 1. Setup Users
        try:
            akhil_user = User.objects.get(username='akhil')
            krishna_user = User.objects.get(username='krishna')
            karthik_user = User.objects.get(username='karthik')
            hrishikesh_user = User.objects.get(username='hrishikesh')
            john_user = User.objects.get(username='john') # The Bad Actor Target
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("Users not found. Run seed_users first."))
            return

        john_upi = john_user.profile.upi_id
        
        # 2. Normal Transaction (Akhil -> John)
        self.stdout.write("\n--- Test 1: Normal Transaction (Akhil -> John) ---")
        amount = Decimal('100.00')
        # Simulate analyze_risk call directly as views would
        is_suspicious, score, status, debug = analyze_risk(
            sender=akhil_user, 
            amount=amount, 
            city="Mumbai", 
            receiver_upi_id=john_upi,
            current_lat=19.07, current_lon=72.87 # Mumbai coords
        )
        self.stdout.write(f"Result: Status={status}, Suspicious={is_suspicious}")
        
        if status != 'BLOCKED':
            self.stdout.write(self.style.SUCCESS("Transaction Passed (Expected)"))
        else:
            self.stdout.write(self.style.ERROR("Transaction Blocked (Unexpected)"))

        # 3. Report John (Make him a Bad Actor)
        self.stdout.write("\n--- Test 2: Reporting John (4 Reports needed) ---")
        reporters = [akhil_user, krishna_user, karthik_user, hrishikesh_user]
        
        # Clear existing feedbacks for clean test
        Feedback.objects.all().delete()
        
        for i, reporter in enumerate(reporters):
            msg = f"Fraud report against Transaction #999 from {john_upi}"
            Feedback.objects.create(user=reporter, message=msg)
            self.stdout.write(f"Report {i+1} submitted by {reporter.username}")

        # Verify Reports Logic (mimic view logic)
        count = Feedback.objects.filter(message__icontains=john_upi).filter(message__icontains='fraud').count()
        self.stdout.write(f"Total Fraud Reports against John: {count}")
        
        if count > 3:
             self.stdout.write(self.style.SUCCESS("John meets 'Bad Actor' criteria (>3 reports)"))
        else:
             self.stdout.write(self.style.ERROR("John does NOT meet criteria (Check filter logic)"))

        # 4. Bad Actor Transaction (Krishna -> John)
        self.stdout.write("\n--- Test 3: Transaction to Bad Actor (Krishna -> John) ---")
        
        is_suspicious, score, status, debug = analyze_risk(
            sender=krishna_user, 
            amount=amount, 
            city="Chennai", 
            receiver_upi_id=john_upi,
            current_lat=13.08, current_lon=80.27
        )
        self.stdout.write(f"Result: Status={status}, Suspicious={is_suspicious}, Score={score}")

        if status == 'BLOCKED' and score >= 100:
            self.stdout.write(self.style.SUCCESS("Transaction BLOCKED by Bad Actor Logic (Expected)"))
        else:
            self.stdout.write(self.style.ERROR(f"Transaction NOT Blocked (Unexpected). Status: {status}"))

        self.stdout.write("\nSimulation Complete.")
