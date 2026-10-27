
import os
import django
import sys
from decimal import Decimal

# Setup Django environment
sys.path.append(r'c:\Users\vnakh\OneDrive\Documents\django projects\ongoing\upi\Fraudshield')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fraudshield.settings')
django.setup()

from upi_app.models import Transaction, UserProfile
from upi_app.views import analyze_risk
from django.contrib.auth.models import User

def debug_transactions():
    transactions = Transaction.objects.all().order_by('id')
    print(f"{'ID':<5} | {'Sender':<15} | {'Amount':<10} | {'Status':<15} | {'PIN Time':<10} | {'Suspicious':<10}")
    print("-" * 80)
    for txn in transactions:
        print(f"{txn.id:<5} | {txn.sender.username:<15} | {txn.amount:<10} | {txn.status:<15} | {txn.pin_time_taken:<10.2f} | {txn.is_suspicious:<10}")

def simulate_ai_logic(username, amount, pin_time):
    try:
        user = User.objects.get(username=username)
        print(f"\nSimulating Risk Analysis for {username} | Amount: {amount} | PIN Time: {pin_time}")
        is_suspicious, score, status, debug_info = analyze_risk(
            user, 
            Decimal(str(amount)), 
            "Unknown", 
            "test@upi", 
            0.0, 0.0, 
            "127.0.0.1", 
            float(pin_time)
        )
        print(f"Result: {status} | Suspicious: {is_suspicious} | Score: {score:.4f}")
        print(f"Debug Info: {debug_info}")
    except Exception as e:
        print(f"Error simulating AI: {e}")

if __name__ == "__main__":
    users = User.objects.filter(is_superuser=False)
    if users.exists():
        test_user = users.first().username
        user_obj = User.objects.get(username=test_user)
        
        # Create a "last transaction" in a far away place to trigger Impossible Travel
        from upi_app.models import Transaction
        from django.utils import timezone
        from datetime import timedelta
        
        # Clear existing history for test
        Transaction.objects.filter(sender=user_obj).delete()
        
        Transaction.objects.create(
            sender=user_obj,
            receiver_upi_id="other@upi",
            amount=10,
            status='SUCCESS',
            location_lat=12.9716, # Bangalore
            location_lon=77.5946,
            timestamp=timezone.now() - timedelta(minutes=10) # 10 mins ago
        )
        
        # Scenario: Trigger Impossible Travel (Bangalore to London in 10 mins)
        print(f"\n--- Testing Hard Block Lockout (Impossible Travel) ---")
        is_suspicious, score, status, debug_info = analyze_risk(user_obj, 100, "Unknown", "other@upi", 0.0, 0.0, "1.1.1.1", 2.0)
        print(f"Result: {status} | Debug: {debug_info}")
        
        if status == 'BLOCKED' and "Community Block" not in debug_info:
            from datetime import timedelta
            user_obj.profile.account_locked_until = timezone.now() + timedelta(hours=48)
            user_obj.profile.save()
            print("Action: Account locked in simulation.")
        
        # Re-fetch profile to check lockout
        user_obj.profile.refresh_from_db()
        locked = user_obj.profile.account_locked_until
        print(f"\nAccount Locked Until: {locked}")
        
        if locked:
            diff = locked - timezone.now()
            print(f"Lockout remaining: {diff.total_seconds() / 3600:.1f} hours")
        else:
            print("Lockout FAILED")




