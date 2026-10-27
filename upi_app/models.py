from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    upi_id = models.CharField(max_length=50, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_verified = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # AI Risk Analysis Fields
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    trust_score = models.FloatField(default=100.0)
    
    # New Security Fields
    pin = models.CharField(max_length=6, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    pin_failed_attempts = models.IntegerField(default=0)
    pin_locked_until = models.DateTimeField(blank=True, null=True)
    account_locked_until = models.DateTimeField(blank=True, null=True)


    # Merchant / Business Fields
    is_merchant = models.BooleanField(default=False)
    business_name = models.CharField(max_length=100, blank=True, null=True)
    business_category = models.CharField(max_length=50, blank=True, null=True) # e.g. Hospital, Pharmacy, Retail
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    document_proof = models.ImageField(upload_to='merchant_docs/', blank=True, null=True)
    
    VERIFICATION_STATUS = [
        ('UNVERIFIED', 'Unverified'),
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='UNVERIFIED')
    ai_verification_score = models.FloatField(default=0.0)
    ai_verification_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.upi_id}"

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
        ('BLOCKED', 'Blocked'),
        ('PENDING_VERIFICATION', 'Pending Verification'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_transactions')
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transactions')
    receiver_upi_id = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')
    
    # AI Risk Analysis Fields
    fraud_score = models.FloatField(default=0.0)
    is_suspicious = models.BooleanField(default=False)
    device_id = models.CharField(max_length=100, blank=True, null=True)
    otp_attempts = models.IntegerField(default=0)
    category = models.CharField(max_length=50, blank=True, null=True)
    pin_time_taken = models.FloatField(default=0.0) # Seconds to enter PIN
    
    # New Location Fields for AI
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    location_lon = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)

    def __str__(self):
        return f"Txn #{self.id} - {self.sender.username} to {self.receiver_upi_id} - {self.amount}"

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    admin_reply = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Feedback by {self.user.username} on {self.created_at.strftime('%Y-%m-%d')}"

class LocationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='location_history')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} at {self.latitude}, {self.longitude} ({self.timestamp})"
