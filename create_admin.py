import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fraudshield.settings')
django.setup()

from django.contrib.auth.models import User

try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("CREATED: admin / admin123")
    else:
        u = User.objects.get(username='admin')
        u.set_password('admin123')
        u.is_staff = True
        u.is_superuser = True
        u.save()
        print("RESET: admin / admin123")
except Exception as e:
    print(f"ERROR: {e}")
