from django.core.management.base import BaseCommand
from upi_app.models import Feedback

class Command(BaseCommand):
    help = 'Deletes fraud reports containing old @fraudshield format'

    def handle(self, *args, **kwargs):
        # We look for messages containing the old domain
        count, _ = Feedback.objects.filter(message__icontains='@fraudshield').delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} old fraud reports containing '@fraudshield'."))
