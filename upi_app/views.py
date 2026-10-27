from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
import random
from django.utils import timezone
from .models import UserProfile, Transaction, LocationHistory, Feedback
from datetime import datetime
from decimal import Decimal
import re

import math
from datetime import timedelta
from django.db.models import Avg, Q
from .ocr_utils import verify_document

# --- Risk Analysis Logic ---
def calculate_distance(lat1, lon1, lat2, lon2):
    # Earth radius in KM
    R = 6371.0
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c # Distance in KM

from sklearn.ensemble import IsolationForest
import numpy as np
import pandas as pd
import os

# Global model loading removed.


def analyze_risk(user, amount, city, receiver_upi_id, current_lat=0.0, current_lon=0.0, current_ip=None, pin_time_taken=0.0):
    """
    Analyzes transaction details using Personalized Isolation Forest.
    Categorizes results into Identity Risk and Intent Risk.
    """
    identity_anomaly = False
    intent_anomaly = False
    
    fraud_score = 1.0 # Default to Normal
    status = 'PENDING'
    sender_profile = user.profile
    debug_info = ""

    # 1. Fetch History (Last 50 transactions)
    history = Transaction.objects.filter(sender=user).exclude(status='FAILED').order_by('-timestamp')[:50]
    
    # 2. Build Features
    current_time = timezone.now()
    current_hour = current_time.hour
    
    history_list = list(history)
    
    # helper for time difference
    def get_time_diff(t1, t2):
        return (t1 - t2).total_seconds()

    # Calculate DistFromAvgLoc and Travel Speed
    last_txn = history_list[0] if history_list else None
    travel_speed = 0.0
    
    past_lats = [float(t.location_lat) for t in history_list if t.location_lat != 0]
    past_lons = [float(t.location_lon) for t in history_list if t.location_lon != 0]
    
    if past_lats and past_lons:
        avg_lat = sum(past_lats) / len(past_lats)
        avg_lon = sum(past_lons) / len(past_lons)
        dist_from_pattern = calculate_distance(avg_lat, avg_lon, current_lat, current_lon)
    else:
        last_loc = LocationHistory.objects.filter(user=user).order_by('-timestamp').first()
        if last_loc:
             dist_from_pattern = calculate_distance(float(last_loc.latitude), float(last_loc.longitude), current_lat, current_lon)
        else:
             dist_from_pattern = 0.0

    if last_txn and last_txn.location_lat != 0:
        dist_km = calculate_distance(float(last_txn.location_lat), float(last_txn.location_lon), current_lat, current_lon)
        time_diff_hours = get_time_diff(current_time, last_txn.timestamp) / 3600.0
        if time_diff_hours > 0:
            travel_speed = dist_km / time_diff_hours

    # Calculate TimeSinceLast
    if last_txn:
        time_since_last = get_time_diff(current_time, last_txn.timestamp)
    else:
        time_since_last = 3600 * 24 
        
    # Receiver Freq
    receiver_count = sum(1 for t in history_list if t.receiver_upi_id == receiver_upi_id)
    is_new_receiver = 1 if receiver_count == 0 else 0
    
    # Current Features: [Amount, Hour, TimeSinceLast, DistFromPattern, IsNewReceiver, PINTime]
    current_features = [float(amount), float(current_hour), float(time_since_last), float(dist_from_pattern), float(is_new_receiver), float(pin_time_taken)]

    # Identity Risk Checks (Identity Breaches)
    if travel_speed > 800:
        identity_anomaly = True
        debug_info += f"Identity Breach: Impossible Travel ({travel_speed:.0f} km/h) | "

    # 3. AI Analysis & Heuristic Fallbacks
    if len(history_list) >= 2:
        X_train = []
        for i, txn in enumerate(history_list):
            amt = float(txn.amount)
            hr = txn.timestamp.hour
            t_diff = get_time_diff(txn.timestamp, history_list[i+1].timestamp) if i + 1 < len(history_list) else 3600 * 24
            
            t_lat = float(txn.location_lat)
            t_lon = float(txn.location_lon)
            
            # Use current_lat/lon variables if avg_lat is not in scope yet
            dist = calculate_distance(current_lat, current_lon, t_lat, t_lon) if (t_lat != 0) else 0.0
            
            is_new_rcv = 0 
            pin_t = float(txn.pin_time_taken)
            X_train.append([amt, float(hr), float(t_diff), dist, float(is_new_rcv), pin_t])

        clf = IsolationForest(n_estimators=50, contamination=0.25, random_state=42, n_jobs=-1)
        clf.fit(X_train)
        
        score_array = clf.decision_function([current_features])
        fraud_score = score_array[0]
        
        # Identity Anomaly: PIN Timing Check (Tightened to 4s)
        avg_pin = sum(t[5] for t in X_train) / len(X_train)
        if abs(pin_time_taken - avg_pin) > 4: 
            identity_anomaly = True
            debug_info += f"Identity Anomaly: PIN Timing ({pin_time_taken:.1f}s vs avg {avg_pin:.1f}s) | "
        
        # Identity Anomaly: Location Shift (100km)
        if dist_from_pattern > 100:
            identity_anomaly = True
            debug_info += f"Identity Anomaly: Location Shift ({dist_from_pattern:.0f}km) | "

        # AI Anomaly Score Check
        if fraud_score < 0:
            if not identity_anomaly:
                intent_anomaly = True
                debug_info += f"AI Intent Anomaly (Score: {fraud_score:.2f}) | "
        
        # Heuristic Jump Check: If amount is > 10x the historical average
        avg_amt = sum(t[0] for t in X_train) / len(X_train)
        if amount > Decimal(str(avg_amt)) * 5: # Even 5x is suspicious enough for OTP
            intent_anomaly = True
            debug_info += f"Heuristic Warning: Large amount jump ({amount} vs avg {avg_amt:.2f}) | "

    else:
        # Cold Start: No or very little history
        if amount > 1000:
            intent_anomaly = True
            debug_info += "Heuristic Warning: First large transaction for new user | "
        
        if len(history_list) == 1:
            prev_amt = float(history_list[0].amount)
            if amount > Decimal(str(prev_amt)) * 5:
                intent_anomaly = True
                debug_info += f"Heuristic Warning: Significant jump from last txn ({amount} vs {prev_amt}) | "

        
        print(f"[AI] User: {user.username} | Score: {fraud_score:.4f} | Identity: {identity_anomaly} | Intent: {intent_anomaly}")

    # Final Decision Mapping
    if identity_anomaly:
        status = 'BLOCKED'
        debug_info = f"AI Hard Block: {debug_info}"
    elif intent_anomaly:
        status = 'PENDING_VERIFICATION'
        debug_info = f"AI Warning: {debug_info}"
    else:
        status = 'SUCCESS'
        debug_info = "AI Safe"

    # Community Block
    fraud_reports_count = Feedback.objects.filter(
        message__icontains=receiver_upi_id
    ).filter(
        message__icontains='fraud'
    ).count()
    
    if fraud_reports_count >= 3:
        status = 'BLOCKED'
        debug_info += " + Community Block (Reported User)"

    return identity_anomaly or intent_anomaly, fraud_score, status, debug_info

# --- User Views (Reloader Trigger) ---

def home(request):
    return render(request, 'user/home.html')

def about(request):
    return render(request, 'user/about.html')

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

def login_view(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        
        user = None
        
        # Check if input is email
        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email=username_or_email)
                username = user_obj.username
            except User.DoesNotExist:
                username = None
        else:
            username = username_or_email
            
        if username:
            user = authenticate(request, username=username, password=password)
            
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Capture Location on Login (IP Based)
            # disabled to avoid cluttering history for speed test
            # lat, lon, city = get_ip_location()
                
            # LocationHistory.objects.create(
            #     user=user,
            #     latitude=lat,
            #     longitude=lon,
            #     ip_address=request.META.get('REMOTE_ADDR'),
            #     city="Login Location" 
            # )
            
            # Redirect Admins to Admin Dashboard
            if user.is_superuser or user.is_staff:
                return redirect('admin_dashboard')
            else:
                return redirect('user_dashboard')
        else:
            messages.error(request, "Invalid credentials. Please try again.")
            
    return render(request, 'user/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')

def register(request):
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')
        location = request.POST.get('location')
        pin = request.POST.get('pin')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email ID already exists.")
            return redirect('register')
        
        if UserProfile.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Phone number already exists.")
            return redirect('register')
        
        try:
            # Create User
            username = email.split('@')[0]
            # Ensure unique username
            if User.objects.filter(username=username).exists():
                username = f"{username}_{datetime.now().strftime('%f')[:4]}"

            user = User.objects.create_user(username=username, email=email, password=password)
            user.first_name = fullname
            user.save()

            # Create Profile
            # Generate a random UPI ID for demo
            upi_id = f"{username}@upi"
            
            is_merchant = request.POST.get('is_merchant') == 'on'
            business_name = request.POST.get('business_name')
            business_category = request.POST.get('business_category')
            registration_number = request.POST.get('registration_number')
            document_proof = request.FILES.get('document_proof')
            
            profile = UserProfile.objects.create(
                user=user,
                upi_id=upi_id,
                phone_number=phone_number,
                location=location,
                pin=pin,
                balance=100000.00, # Sign up bonus/demo balance
                is_merchant=is_merchant,
                business_name=business_name if is_merchant else None,
                business_category=business_category if is_merchant else None,
                registration_number=registration_number if is_merchant else None,
                document_proof=document_proof if is_merchant else None,
                verification_status='PENDING' if is_merchant else 'UNVERIFIED'
            )
            
            if is_merchant and document_proof:
                try:
                    # Run OCR Verification
                    score, notes, extracted_text = verify_document(
                        profile.document_proof.path,
                        business_name,
                        registration_number
                    )
                    profile.ai_verification_score = score
                    # Ensure notes are saved as a string for consistency
                    if isinstance(notes, list):
                        profile.ai_verification_notes = " | ".join(notes)
                    else:
                         profile.ai_verification_notes = str(notes)
                    profile.save()
                    print(f"Merchant Registration: {username} | OCR Score: {score}")
                except Exception as e:
                    print(f"OCR Verification Failed: {str(e)}")

            login(request, user)
            messages.success(request, "Account created successfully! Welcome to FraudShield.")
            return redirect('user_dashboard')

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect('register')

    return render(request, 'user/register.html')

@login_required
def user_dashboard(request):
    return render(request, 'user/user.html')

@login_required
def profile(request):
    if request.method == 'POST':
        user = request.user
        profile = user.profile

        # Update User fields
        user.email = request.POST.get('email', user.email)
        user.save()

        # Update Profile fields
        profile.phone_number = request.POST.get('phone', profile.phone_number)
        profile.location = request.POST.get('location', profile.location)
        
        # Update PIN
        pin = request.POST.get('pin')
        if pin:
            profile.pin = pin

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    has_pin = bool(request.user.profile.pin)
    return render(request, 'user/profile.html', {'has_pin': has_pin})

@login_required
def verify_account(request):
    if request.user.profile.is_verified or request.user.profile.verification_status == 'VERIFIED':
        messages.info(request, "Your account is already verified.")
        return redirect('profile')

    step = request.POST.get('step', 'pan')
    pan_number = request.POST.get('pan_number', '').strip().upper()
    
    if request.method == 'POST':
        if step == 'pan':
            # Simulate PAN validation
            if not pan_number or len(pan_number) < 10:
                messages.error(request, "Please enter a valid 10-digit PAN number.")
                return render(request, 'user/verify.html', {'step': 'pan', 'pan_number': pan_number})
            
            # Simulate sending OTP
            generated_otp = str(random.randint(100000, 999999))
            phone = request.user.profile.phone_number or "1234567890"
            # Ensure phone is at least 4 digits for obfuscation
            if len(phone) < 4:
                phone = "0000000000"
            phone_obfuscated = f"+91 {phone[:2]}******{phone[-2:]}"
            
            return render(request, 'user/verify.html', {
                'step': 'otp',
                'pan_number': pan_number,
                'generated_otp': generated_otp,
                'phone_obfuscated': phone_obfuscated
            })
            
        elif step == 'otp':
            user_otp = "".join([
                request.POST.get('otp1', ''),
                request.POST.get('otp2', ''),
                request.POST.get('otp3', ''),
                request.POST.get('otp4', ''),
                request.POST.get('otp5', ''),
                request.POST.get('otp6', '')
            ])
            generated_otp = request.POST.get('generated_otp')
            phone_obfuscated = request.POST.get('phone_obfuscated')
            
            if user_otp == generated_otp:
                profile = request.user.profile
                profile.is_verified = True
                profile.save()
                messages.success(request, "Account verified successfully!")
                return redirect('user_dashboard')
            else:
                messages.error(request, "Invalid OTP. Please try again.")
                return render(request, 'user/verify.html', {
                    'step': 'otp',
                    'pan_number': pan_number,
                    'generated_otp': generated_otp,
                    'phone_obfuscated': phone_obfuscated
                })

    return render(request, 'user/verify.html', {'step': 'pan'})

import urllib.request
import json
import traceback

def get_ip_location():
    """
    Fetches location based on public IP address with Fallback.
    """
    # Primary: ip-api.com (HTTP)
    try:
        print("DEBUG: Trying ip-api.com...")
        with urllib.request.urlopen("http://ip-api.com/json/", timeout=3) as url:
            data = json.loads(url.read().decode())
            if data['status'] == 'success':
                return float(data['lat']), float(data['lon']), data['city']
    except Exception as e:
        print(f"DEBUG: ip-api failed: {e}")

    import ssl
    # Bypass SSL verification for legacy/dev environments
    ssl_context = ssl._create_unverified_context()

    # Backup: ipwho.is (HTTPS)
    try:
        print("DEBUG: Trying ipwho.is (Backup)...")
        # specific header to avoid 403 checks sometimes
        req = urllib.request.Request(
            "https://ipwho.is/", 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as url:
            data = json.loads(url.read().decode())
            if data.get('success', False):
                return float(data['latitude']), float(data['longitude']), data['city']
            else:
                 return 0.0, 0.0, f"Backup-Fail: {data.get('message')}"
    except Exception as e:
        print(f"DEBUG: ipwho.is failed: {e}")
        return 0.0, 0.0, f"Net-Err: {str(e)}" # Show specific error

    return 0.0, 0.0, "Unknown-Final"

@login_required
def balance(request):
    return render(request, 'user/balance.html')

@login_required
def history(request):
    transactions = Transaction.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by('-timestamp')

    # Identify reported transactions from feedback
    user_feedbacks = Feedback.objects.filter(user=request.user)
    reported_txn_ids = set()
    for fb in user_feedbacks:
        match = re.search(r'Transaction #(\d+)', fb.message)
        if match:
            reported_txn_ids.add(int(match.group(1)))

    for txn in transactions:
        txn.is_reported = txn.id in reported_txn_ids

    return render(request, 'user/history.html', {'transactions': transactions})

@login_required
def send_money(request):
    if request.method == 'POST':
        profile = request.user.profile
        # Check PIN Lockout
        if profile.pin_locked_until and profile.pin_locked_until > timezone.now():
            diff = profile.pin_locked_until - timezone.now()
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            messages.error(request, f"Your PIN is locked due to too many failed attempts. Please try again in {hours}h {minutes}m.")
            return redirect('user_dashboard')

        # Check Account Hard Lockout (48 hours)
        if profile.account_locked_until and profile.account_locked_until > timezone.now():
            diff = profile.account_locked_until - timezone.now()
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            messages.error(request, f"Your account is temporarily locked due to suspicious activity. Please try again in {hours}h {minutes}m.")
            return redirect('user_dashboard')


        receiver_upi = request.POST.get('upi_id')
        amount_str = request.POST.get('amount')
        description = request.POST.get('description')
        category = request.POST.get('category')
        
        try:
            amount = Decimal(amount_str)
            sender_profile = request.user.profile
            receiver_profile = UserProfile.objects.filter(upi_id=receiver_upi).first()
            
            # Basic Validation
            if not receiver_profile:
                messages.error(request, 'Receiver UPI ID not found.')
                return redirect('send_money')
            
            if sender_profile.balance < amount:
                messages.error(request, 'Insufficient balance.')
                return redirect('send_money')

            # Store Transaction Details in Session for Verification
            request.session['pending_txn'] = {
                'receiver_upi': receiver_upi,
                'amount': str(amount), # Decimal not JSON serializable
                'description': description,
                'category': category
            }
            
            return redirect('verify_pin') 

        except Exception as e:
            traceback.print_exc()
            messages.error(request, f"Error initializing transaction: {str(e)}")
            return redirect('send_money')

    return render(request, 'user/send.html')

@login_required
def verify_pin(request):
    profile = request.user.profile
    if profile.pin_locked_until and profile.pin_locked_until > timezone.now():
        # ... existing messages ...
        return redirect('user_dashboard')

    if profile.account_locked_until and profile.account_locked_until > timezone.now():
        messages.error(request, "Your account is temporarily locked due to suspicious activity.")
        return redirect('user_dashboard')


    if request.method == 'POST':
        pin_entered = request.POST.get('pin')
        user_pin = getattr(request.user.profile, 'pin', None)
        
        if not user_pin:
             messages.error(request, "You have not set a transaction PIN. Please update your profile.")
             return redirect('user_dashboard') # Or profile settings

        if pin_entered == user_pin:
            # Success - Reset Attempts
            profile.pin_failed_attempts = 0
            profile.pin_locked_until = None
            profile.save()
            
            request.session['pin_attempts'] = 0
            
            # Bot Detection: Machine Gun Frequency (Max 5 transactions per minute)
            one_minute_ago = timezone.now() - timedelta(minutes=1)
            recent_txns_count = Transaction.objects.filter(
                sender=request.user,
                timestamp__gte=one_minute_ago,
                status='SUCCESS'
            ).count()

            if recent_txns_count >= 5:
                messages.error(request, "Bot Attack Detected! Too many transactions in a short time. Please wait a minute.")
                if 'pending_txn' in request.session:
                    del request.session['pending_txn']
                return redirect('user_dashboard')

            # PIN Verified - Execute Transaction
            txn_data = request.session.get('pending_txn')
            if not txn_data:
                messages.error(request, "Session expired or invalid transaction.")
                return redirect('send_money')

            # Determine Risk and Process
            try:
                receiver_upi = txn_data['receiver_upi']
                amount = Decimal(txn_data['amount'])
                description = txn_data['description']
                category = txn_data.get('category')
                
                receiver_profile = UserProfile.objects.get(upi_id=receiver_upi)
                sender_profile = request.user.profile

                 # IP Location Detection (Real-time)
                lat, lon, city_detected = get_ip_location()
                # Use registered location if detection fails or as fallback context? 
                # Request says "don't change existing conditions", so we rely on IP logic as prime.
                city = city_detected if city_detected != "Unknown" else "Unknown"
                current_ip = request.META.get('REMOTE_ADDR')
                
                # Keystroke Dynamics
                try:
                    pin_time_taken = float(request.POST.get('time_taken', 0))
                except:
                    pin_time_taken = 0.0

                is_suspicious, score, status, debug_info = analyze_risk(request.user, amount, city, receiver_upi, lat, lon, current_ip, pin_time_taken)

                # Save Location History
                LocationHistory.objects.create(
                    user=request.user,
                    latitude=lat, 
                    longitude=lon,
                    ip_address=current_ip,
                    city=city
                )

                with transaction.atomic():
                    # High Risk Evaluation Logic
                    if status == 'PENDING_VERIFICATION':
                        # Intent Anomaly - Allow OTP
                        txn = Transaction.objects.create(
                            sender=request.user,
                            receiver=receiver_profile.user,
                            receiver_upi_id=receiver_upi,
                            amount=amount,
                            description=description,
                            category=category,
                            status=status,
                            fraud_score=score,
                            is_suspicious=True,
                            device_id=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                            location_lat=lat,
                            location_lon=lon,
                            pin_time_taken=pin_time_taken
                        )
                        del request.session['pending_txn'] # Clear session
                        messages.warning(request, f"this is suspicious and go on with your own risk ({debug_info})")
                        return redirect('verify_emergency', txn_id=txn.id)
                        
                    elif status == 'BLOCKED':
                        # Identity Breach or Community Block - Hard Block
                        del request.session['pending_txn'] # Clear session
                        if "Community Block" in debug_info:
                             messages.error(request, f"transaction blocked, this user is reported by other users ({debug_info})")
                        else:
                             # Set 48-hour lockout for non-community blocks (Identity anomalies)
                             sender_profile.account_locked_until = timezone.now() + timedelta(hours=48)
                             sender_profile.save()
                             messages.error(request, f"Suspicious behavior detected. Your account has been locked for 48 hours for your security. ({debug_info})")
                        return redirect('user_dashboard')


                    else:
                        # Success Flow
                        sender_profile.balance -= amount
                        sender_profile.total_spent += amount
                        sender_profile.save()
                        
                        receiver_profile.balance += amount
                        receiver_profile.save()

                        status = 'SUCCESS'
                        
                        txn = Transaction.objects.create(
                            sender=request.user,
                            receiver=receiver_profile.user,
                            receiver_upi_id=receiver_upi,
                            amount=amount,
                            description=description,
                            category=category,
                            status=status,
                            fraud_score=score,
                            is_suspicious=is_suspicious,
                            device_id=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                            location_lat=lat,
                            location_lon=lon,
                            pin_time_taken=pin_time_taken
                        )
                        
                        del request.session['pending_txn'] # Clear session
                        
                        messages.success(request, f"Transaction Successful! Paid ₹{amount} to {receiver_upi}")
                        if debug_info and "Safe" not in debug_info:
                             messages.success(request, debug_info) # Show debug info for demo
                        return redirect('user_dashboard')
                        
            except Exception as e:
                traceback.print_exc()
                messages.error(request, f"Transaction failed during processing: {str(e)}")
                return redirect('user_dashboard')

        else:
            # Incorrect PIN Logic - Persistent Tracking
            profile.pin_failed_attempts += 1
            
            if profile.pin_failed_attempts >= 3:
                # Max Attempts Reached - Block for 24 hours
                profile.pin_locked_until = timezone.now() + timedelta(days=1)
                profile.save()
                
                if 'pending_txn' in request.session:
                    del request.session['pending_txn']
                
                messages.error(request, "Too many incorrect PIN attempts. Your account has been locked for 24 hours for security.")
                return redirect('user_dashboard')
            else:
                profile.save()
                remaining = 3 - profile.pin_failed_attempts
                messages.error(request, f"Incorrect PIN. You have {remaining} attempt(s) remaining before a 24-hour lockout.")
                return redirect('verify_pin') # Allow retry

    return render(request, 'user/pin.html')

@login_required
def feedback(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        if message:
            # Prevent duplicate report via POST
            match = re.search(r'Transaction #(\d+)', message)
            if match:
                 txn_id = int(match.group(1))
                 existing = Feedback.objects.filter(user=request.user, message__icontains=f"Transaction #{txn_id}").exists()
                 if existing:
                     messages.warning(request, "Discarded: You have already reported this transaction.")
                     return redirect('user_dashboard')

                 # Deduct Trust Score from the Receiver (Reported User)
                 try:
                     txn = Transaction.objects.get(id=txn_id)
                     # Ensure we don't punish if sender reports themselves (unlikely but possible via manual ID entry)
                     if txn.receiver and txn.receiver != request.user:
                         receiver_profile = txn.receiver.profile
                         old_score = receiver_profile.trust_score
                         receiver_profile.trust_score = max(0.0, receiver_profile.trust_score - 20.0)
                         receiver_profile.save()
                         print(f"DEBUG: Report on Txn #{txn.id}. User {txn.receiver.username} score: {old_score} -> {receiver_profile.trust_score}")
                 except Transaction.DoesNotExist:
                     pass

            Feedback.objects.create(user=request.user, message=message)
            messages.success(request, 'Feedback submitted successfully!')
            return redirect('user_dashboard')
    
    # Handle optional report parameter
    default_message = ""
    report_txn_id = request.GET.get('report')
    if report_txn_id:
        try:
            txn = Transaction.objects.get(id=report_txn_id, sender=request.user)
            
            # Check for duplicate report
            existing_feedbacks = Feedback.objects.filter(user=request.user)
            for fb in existing_feedbacks:
                match = re.search(r'Transaction #(\d+)', fb.message)
                if match and int(match.group(1)) == txn.id:
                     messages.warning(request, "You have already reported this transaction.")
                     return redirect('history')

            default_message = f"I want to report fraud regarding Transaction #{txn.id} sent to {txn.receiver_upi_id}. Details: "
        except Transaction.DoesNotExist:
            default_message = f"I want to report an issue with Transaction #{report_txn_id}. Details: "

    # Fetch user's feedback history
    user_feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'user/feedback.html', {'user_feedbacks': user_feedbacks, 'default_message': default_message})

@login_required
def verify_emergency(request, txn_id):
    txn = get_object_or_404(Transaction, id=txn_id, sender=request.user)
    
    if txn.status != 'PENDING_VERIFICATION':
         messages.error(request, "This transaction cannot be verified.")
         return redirect('user_dashboard')
         
    return render(request, 'user/verify_emergency.html', {'txn': txn})

@login_required
def finalize_emergency_pay(request, txn_id):
    txn = get_object_or_404(Transaction, id=txn_id, sender=request.user)
    
    if request.method == 'POST':
        # Check if already blocked
        if txn.status == 'BLOCKED' or txn.otp_attempts >= 3:
             messages.error(request, "This transaction has been permanently blocked due to multiple incorrect attempts.")
             return redirect('user_dashboard')

        generated_otp = request.POST.get('generated_otp')
        user_otp = request.POST.get('user_otp')
        
        if generated_otp and user_otp and generated_otp == user_otp:
            # Verification Success
            with transaction.atomic():
                # Re-fetch profile for balance check safety
                sender_profile = request.user.profile
                if sender_profile.balance >= txn.amount:
                    sender_profile.balance -= txn.amount
                    sender_profile.total_spent += txn.amount
                    sender_profile.save()
                    
                    # Credit Receiver
                    if txn.receiver:
                        txn.receiver.profile.balance += txn.amount
                        txn.receiver.profile.save()
                    
                    txn.status = 'SUCCESS'
                    txn.save()
                    
                    messages.success(request, f"Emergency Payment of ₹{txn.amount} Successful.")
                else:
                    txn.status = 'FAILED'
                    txn.save()
                    messages.error(request, "Insufficient balance during finalization.")
        else:
            # Incorrect Verification Code
            txn.otp_attempts += 1
            if txn.otp_attempts >= 3:
                txn.status = 'BLOCKED'
                txn.otp_attempts = 3 # Cap it for visual if needed
                txn.save()
                messages.error(request, "Transaction BLOCKED: multiple incorrect OTP attempts.")
                return redirect('user_dashboard')
            else:
                txn.save()
                remaining = 3 - txn.otp_attempts
                messages.error(request, f"Incorrect Verification Code. {remaining} attempts remaining.")
                return redirect('verify_emergency', txn_id=txn.id)
            
            
    return redirect('user_dashboard')

# --- Admin Views ---
# Assuming admin views require admin access, but keeping simple for now
@login_required
def admin_dashboard(request):
    return render(request, 'admin/admin_dashboard.html')

@login_required
def manage_users(request):
    # Fetch all users who are not superusers
    all_profiles = UserProfile.objects.filter(user__is_superuser=False).select_related('user')
    
    merchants = all_profiles.filter(is_merchant=True)
    
    # Process notes for display
    for m in merchants:
        if m.ai_verification_notes:
            # Handle potential different formats (list string or pipe-separated)
            notes_str = str(m.ai_verification_notes)
            if ' | ' in notes_str:
                m.notes_list = notes_str.split(' | ')
            elif notes_str.startswith('[') and notes_str.endswith(']'):
                # Cleanup list string representation if it exists
                import ast
                try:
                    m.notes_list = ast.literal_eval(notes_str)
                except:
                    m.notes_list = [notes_str]
            else:
                m.notes_list = [notes_str]
        else:
            m.notes_list = []

    regular_users = all_profiles.filter(is_merchant=False)
    
    return render(request, 'admin/manage_users.html', {
        'merchants': merchants,
        'regular_users': regular_users
    })

@login_required
def view_feedbacks(request):
    pending_feedbacks = Feedback.objects.filter(admin_reply__isnull=True).order_by('-created_at') | Feedback.objects.filter(admin_reply__exact='').order_by('-created_at')
    replied_feedbacks = Feedback.objects.exclude(admin_reply__isnull=True).exclude(admin_reply__exact='').order_by('-created_at')
    
    return render(request, 'admin/view_feedbacks.html', {
        'pending_feedbacks': pending_feedbacks,
        'replied_feedbacks': replied_feedbacks
    })

@login_required
def delete_user(request, user_id):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Access Denied: You are not an admin.')
        return redirect('user_dashboard')

    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=user_id)
        if user_to_delete.is_superuser:
             messages.error(request, "Cannot delete a superuser.")
        else:
            user_to_delete.delete()
            messages.success(request, f'User {user_to_delete.username} has been deleted.')
    return redirect('manage_users')
@login_required
def delete_feedback(request, feedback_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if request.method == 'POST':
        feedback = get_object_or_404(Feedback, id=feedback_id)
        feedback.delete()
        messages.success(request, "Feedback deleted successfully.")
        
    return redirect('view_feedbacks')

@login_required
def reply_feedback(request, feedback_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('home')

    if request.method == 'POST':
        feedback = get_object_or_404(Feedback, id=feedback_id)
        reply_text = request.POST.get('reply')
        
        if reply_text:
            feedback.admin_reply = reply_text
            feedback.save()
            messages.success(request, "Reply sent successfully.")
            
    return redirect('view_feedbacks')

@login_required
def verify_merchant(request, user_id, action):
    if not (request.user.is_superuser or request.user.is_staff):
         messages.error(request, "Access denied.")
         return redirect('user_dashboard')
    
    profile = get_object_or_404(UserProfile, user__id=user_id)
    
    if action == 'approve':
        profile.verification_status = 'VERIFIED'
        profile.save()
        messages.success(request, f"Merchant {profile.business_name} verified successfully.")
    elif action == 'reject':
        profile.verification_status = 'REJECTED'
        profile.save()
        messages.warning(request, f"Merchant {profile.business_name} rejected.")
        
    return redirect('manage_users')

from django.http import JsonResponse

def get_receiver_details(request):
    """
    API to fetch receiver details (Location) based on UPI ID.
    Logic: Use last transaction location if available, else use registered location.
    """
    upi_id = request.GET.get('upi_id')
    if not upi_id:
        return JsonResponse({'success': False, 'error': 'No UPI ID provided'})

    try:
        profile = UserProfile.objects.filter(upi_id=upi_id).first()
        if not profile:
             return JsonResponse({'success': False, 'error': 'UPI ID not found'})
        
        # Check for previous location history
        last_history = LocationHistory.objects.filter(user=profile.user).order_by('-timestamp').first()
        
        if last_history and last_history.city and last_history.city != "Unknown":
            display_location = last_history.city
            source = "Last Active Location"
        else:
            display_location = profile.location
            source = "Registered Location"
            
        return JsonResponse({
            'success': True,
            'location': display_location,
            'source': source,
            'name': profile.user.first_name,
            'is_verified': profile.is_verified or profile.verification_status == 'VERIFIED'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def expense_summary(request):
    # Retrieve user transactions
    txns = Transaction.objects.filter(sender=request.user, status='SUCCESS')
    
    # Calculate spending by category
    spending = {}
    total_spent = Decimal('0.00')
    
    for txn in txns:
        cat = txn.category if txn.category else "Uncategorized"
        spending[cat] = spending.get(cat, Decimal('0.00')) + txn.amount
        total_spent += txn.amount
        
    chart_labels = list(spending.keys())
    chart_data = [float(amount) for amount in spending.values()]

    return render(request, 'user/expense_summary.html', {
        'spending': spending,
        'total_spent': total_spent,
        'chart_labels': chart_labels,
        'chart_data': chart_data
    })
