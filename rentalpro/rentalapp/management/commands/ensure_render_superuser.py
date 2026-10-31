import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the configured Render administrator if it does not already exist.'

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', '').strip()
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '')

        if not any((username, email, password)):
            self.stdout.write(self.style.WARNING(
                'Render admin creation skipped: set DJANGO_SUPERUSER_USERNAME, '
                'DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD.'
            ))
            return

        missing = [
            name
            for name, value in (
                ('DJANGO_SUPERUSER_USERNAME', username),
                ('DJANGO_SUPERUSER_EMAIL', email),
                ('DJANGO_SUPERUSER_PASSWORD', password),
            )
            if not value
        ]
        if missing:
            raise CommandError(
                'Render admin creation requires all three variables; missing '
                + ', '.join(missing)
                + '.'
            )

        user_model = get_user_model()
        existing_user = user_model._default_manager.filter(username=username).first()
        if existing_user:
            if not existing_user.is_superuser:
                raise CommandError(
                    f'The account "{username}" already exists but is not a superuser.'
                )
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{username}" already exists; left unchanged.'
            ))
            return

        user_model._default_manager.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created Render superuser "{username}".'
        ))
