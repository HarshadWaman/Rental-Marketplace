from rentalapp.models import RentalBooking, UserProfile


def user_profile(request):
    profile = None
    pending_rental_requests = 0
    unread_availability_notifications = 0
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        pending_rental_requests = RentalBooking.objects.filter(
            listing__owner=request.user,
            status=RentalBooking.Status.REQUESTED,
        ).count()
        unread_availability_notifications = request.user.rental_availability_notifications.filter(
            read_at__isnull=True,
        ).count()
    return {
        'user_profile': profile,
        'pending_rental_requests': pending_rental_requests,
        'unread_availability_notifications': unread_availability_notifications,
    }
