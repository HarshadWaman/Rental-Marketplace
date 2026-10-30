from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.utils import timezone

from rentalapp.models import RentalAvailabilityNotification, RentalBooking


class Command(BaseCommand):
    help = 'Notify renters by in-app alert and email when an approved rental starts.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        bookings = RentalBooking.objects.filter(
            status=RentalBooking.Status.APPROVED,
            start_date__lte=today,
        ).select_related('renter').order_by('start_date', 'pk')
        sent_count = 0

        for booking in bookings:
            notification, _ = RentalAvailabilityNotification.objects.get_or_create(
                booking=booking,
                defaults={'renter': booking.renter},
            )
            if notification.email_sent_at:
                continue
            if not booking.renter.email:
                raise CommandError(
                    f'Cannot email renter {booking.renter.username}: '
                    'their account has no email address.'
                )

            sent = send_mail(
                subject=f'Your rental is available: {booking.item_title}',
                message=(
                    f'Your rental of {booking.item_title} is available starting '
                    f'{booking.start_date:%B %d, %Y}. '
                    f'Your rental ends on {booking.end_date:%B %d, %Y}.'
                ),
                from_email=None,
                recipient_list=[booking.renter.email],
                fail_silently=False,
            )
            if sent != 1:
                raise CommandError(
                    f'Email notification was not sent for rental request #{booking.pk}.'
                )

            notification.email_sent_at = timezone.now()
            notification.save(update_fields=['email_sent_at'])
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sent {sent_count} rental availability email notification(s).'
        ))
