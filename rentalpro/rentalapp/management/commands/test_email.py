"""
Django management command to test email configuration.

Usage:
    python manage.py test_email recipient@example.com
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Test email configuration by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument(
            'recipient',
            type=str,
            help='Email address to send the test email to'
        )
        parser.add_argument(
            '--subject',
            type=str,
            default='Test Email from Rental Marketplace',
            help='Subject line for the test email'
        )

    def handle(self, *args, **options):
        recipient = options['recipient']
        subject = options['subject']
        
        self.stdout.write('Testing email configuration...')
        self.stdout.write(f'Email Backend: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'Email Host: {settings.EMAIL_HOST}')
        self.stdout.write(f'Email Port: {settings.EMAIL_PORT}')
        self.stdout.write(f'Email Use TLS: {settings.EMAIL_USE_TLS}')
        self.stdout.write(f'Email Host User: {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'Default From Email: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write('')
        
        message = f"""
This is a test email from Rental Marketplace.

If you receive this email, your email configuration is working correctly!

Configuration Details:
- Backend: {settings.EMAIL_BACKEND}
- Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}
- From: {settings.DEFAULT_FROM_EMAIL}

Sent at: {self.get_timestamp()}
        """
        
        try:
            self.stdout.write(f'Sending test email to {recipient}...')
            
            num_sent = send_mail(
                subject=subject,
                message=message.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False
            )
            
            if num_sent > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Test email sent successfully to {recipient}!')
                )
                
                if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                    self.stdout.write(
                        self.style.WARNING(
                            '\nNote: Using console backend. Email printed above instead of sent.'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING('Email was not sent (num_sent = 0)')
                )
                
        except Exception as e:
            raise CommandError(f'Failed to send email: {e}')
    
    def get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
