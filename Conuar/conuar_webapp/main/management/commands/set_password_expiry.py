from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Set password expiry for all existing users (except superusers)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days until password expires (default: 90)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force expiry even for superusers'
        )

    def handle(self, *args, **options):
        days = options['days']
        force = options['force']
        
        # Calculate expiry date
        expiry_date = timezone.now() + timedelta(days=days)
        
        # Get users to update
        if force:
            users = User.objects.all()
            self.stdout.write(f'Setting password expiry for ALL users ({days} days from now)')
        else:
            users = User.objects.filter(is_superuser=False)
            self.stdout.write(f'Setting password expiry for non-superuser accounts ({days} days from now)')
        
        updated_count = 0
        for user in users:
            user.password_expiry_date = expiry_date
            user.password_expired = False
            user.save()
            updated_count += 1
            self.stdout.write(f'  - Updated {user.username} (expires: {expiry_date.strftime("%Y-%m-%d %H:%M")})')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} users with password expiry')
        )
