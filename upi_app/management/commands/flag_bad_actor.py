from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from upi_app.models import Feedback, UserProfile

class Command(BaseCommand):
    help = 'Flags a user as a bad actor by creating fraud reports against them'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username to flag')

    def handle(self, *args, **kwargs):
        target_username = kwargs['username']
        
        try:
            target_user = User.objects.get(username=target_username)
            target_upi = target_user.profile.upi_id
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{target_username}' not found."))
            return

        # Get some reporters (anyone will do, using other users)
        reporters = User.objects.exclude(username=target_username).exclude(is_superuser=True)[:4]
        
        if len(reporters) < 4:
             self.stdout.write(self.style.WARNING("Not enough other users to create unique reports. Creating generic ones."))
             # Fallback if not enough users
        
        self.stdout.write(f"Flagging {target_username} ({target_upi}) as Bad Actor...")
        
        count = 0
        for i in range(4):
            # If we run out of unique reporters, reuse or use first available
            reporter = reporters[i] if i < len(reporters) else reporters[0]
            
            msg = f"Fraud report against {target_upi}. This user is suspicious."
            Feedback.objects.create(user=reporter, message=msg)
            count += 1
            self.stdout.write(f"- Report {count} filed by {reporter.username}")

        self.stdout.write(self.style.SUCCESS(f"Successfully created {count} fraud reports against {target_username}."))
        self.stdout.write(self.style.SUCCESS("They should now be blocked by the Bad Actor Filter."))
