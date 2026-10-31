import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.db.models import Avg, Count
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from rentalapp.forms import (
    RegistrationForm,
    RentalListingForm,
    RentalRequestForm,
    RentalReviewForm,
    LISTING_CATEGORIES,
    ThemeSettingsForm,
    UserAccountForm,
    UserProfileForm,
)
from rentalapp.models import RentalBooking, RentalListing, RentalReview, UserProfile


ITEMS = [
    {
        'pk': 1,
        'title': 'Cordless Impact Drill',
        'city': 'Pune',
        'daily_price': 350,
        'security_deposit': 1500,
        'category': {'name': 'Power tools'},
        'avg_rating': 4.8,
        'review_count': 24,
        'description': 'A reliable cordless impact drill for home repairs, furniture assembly, and weekend projects.',
        'owner': 'Aarav Kulkarni',
        'brand': 'Bosch',
        'condition': 'Excellent',
    },
    {
        'pk': 2,
        'title': 'Pressure Washer',
        'city': 'Mumbai',
        'daily_price': 500,
        'security_deposit': 2000,
        'category': {'name': 'Garden & outdoor'},
        'avg_rating': 4.6,
        'review_count': 18,
        'description': 'Compact pressure washer suitable for patios, vehicles, and outdoor furniture.',
        'owner': 'Meera Shah',
        'brand': 'Karcher',
        'condition': 'Very good',
    },
    {
        'pk': 3,
        'title': 'Professional Ladder',
        'city': 'Pune',
        'daily_price': 180,
        'security_deposit': 800,
        'category': {'name': 'Ladders & access'},
        'avg_rating': 0,
        'review_count': 0,
        'description': 'A sturdy folding ladder for painting, maintenance, and home improvement tasks.',
        'owner': 'Rohan Desai',
        'brand': 'Others',
        'condition': 'Good',
    },
]


BOOKINGS = [
    {
        'item': ITEMS[0],
        'start_date': '28 Oct 2026',
        'end_date': '30 Oct 2026',
        'total_days': 3,
        'status': 'Confirmed',
        'status_badge': 'success',
        'total_price': 1050,
    },
    {
        'item': ITEMS[1],
        'start_date': '02 Nov 2026',
        'end_date': '03 Nov 2026',
        'total_days': 2,
        'status': 'Pending',
        'status_badge': 'warning text-dark',
        'total_price': 1000,
    },
]


def preview_item_list(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    city = request.GET.get('city', '')
    listings = RentalListing.objects.select_related(
        'owner',
        'owner__toolshare_profile',
    ).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating'),
    ).prefetch_related(
        'photos',
        Prefetch(
            'booking_requests',
            queryset=_approved_rentals(),
            to_attr='active_approved_bookings',
        ),
    ).all()
    if query:
        listings = listings.filter(title__icontains=query)
    if category:
        listings = listings.filter(category=category)
    if city:
        listings = listings.filter(city=city)
    items = [_listing_as_item(listing) for listing in listings]
    categories = set(RentalListing.objects.values_list('category', flat=True).distinct())
    cities = set(RentalListing.objects.values_list('city', flat=True).distinct())
    return render(request, 'home.html', {
        'items': items,
        'categories': sorted(categories),
        'cities': sorted(cities),
        'query': query,
        'selected_category': category,
        'selected_city': city,
    })


def preview_item_detail(request, pk=1):
    item = next((item for item in ITEMS if item['pk'] == pk), ITEMS[0])
    form = RentalRequestForm(request.POST or None)
    if request.method == 'POST':
        response = _submit_rental_request(request, item, form)
        if response:
            return response

    return render(request, 'inventory/item_detail.html', {
        'item': item,
        'booking_form': form,
        'booking_url': reverse('ui_preview:item_detail', args=[pk]),
        'can_book': False,
        'is_sample_item': True,
        'reviews': [
            {'author': 'Nisha P.', 'rating': 5, 'date': '12 Oct 2026', 'text': 'Exactly as described and easy to collect. Made the job much quicker.'},
            {'author': 'Kunal R.', 'rating': 4, 'date': '03 Oct 2026', 'text': 'Good tool and helpful owner. Pickup instructions were clear.'},
        ],
    })


def preview_dashboard(request):
    return render(request, 'dashboard/dashboard.html', {
        'bookings': BOOKINGS,
        'active_listings': 3,
        'completed_rentals': 8,
        'pending_requests': 2,
    })


@login_required(login_url='ui_preview:login')
def preview_item_form(request):
    form = RentalListingForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        listing = form.save(commit=False)
        listing.owner = request.user
        listing.save()
        form.save_m2m()
        form.save_uploaded_photos(listing)
        messages.success(request, f"Your listing '{listing.title}' is now live.")
        return redirect('ui_preview:my_listings')
    return render(request, 'inventory/item_form.html', {
        'form': form,
        'categories': _listing_category_suggestions(),
    })


@login_required(login_url='ui_preview:login')
def edit_listing(request, pk):
    listing = get_object_or_404(RentalListing, pk=pk, owner=request.user)
    form = RentalListingForm(
        request.POST or None,
        request.FILES or None,
        instance=listing,
    )
    if request.method == 'POST' and form.is_valid():
        listing = form.save()
        form.save_uploaded_photos(listing)
        messages.success(request, f"Your listing '{listing.title}' has been updated.")
        return redirect('ui_preview:my_listings')
    return render(request, 'inventory/item_form.html', {
        'form': form,
        'listing': listing,
        'is_editing': True,
        'categories': _listing_category_suggestions(),
    })


@login_required(login_url='ui_preview:login')
@require_POST
def delete_listing(request, pk):
    listing = get_object_or_404(RentalListing, pk=pk, owner=request.user)
    title = listing.title
    listing.delete()
    messages.success(request, f"Your listing '{title}' has been deleted.")
    return redirect('ui_preview:my_listings')


def preview_register(request):
    if request.user.is_authenticated:
        return redirect('ui_preview:item_list')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        UserProfile.objects.update_or_create(
            user=user,
            defaults={'phone_number': form.cleaned_data['phone_number']},
        )
        login(request, user)
        messages.success(request, 'Your account has been created. Welcome to ToolShare!')
        return redirect('ui_preview:item_list')

    return render(request, 'accounts/register.html', {'form': form})


@login_required(login_url='ui_preview:login')
def preview_profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    account_form = UserAccountForm(request.POST or None, instance=request.user)
    profile_form = UserProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=user_profile,
    )
    if request.method == 'POST' and account_form.is_valid() and profile_form.is_valid():
        account_form.save()
        profile_form.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('ui_preview:profile')
    return render(request, 'accounts/profile.html', {
        'account_form': account_form,
        'profile_form': profile_form,
        'profile': user_profile,
    })


@login_required(login_url='ui_preview:login')
def my_listings(request):
    listings = RentalListing.objects.filter(owner=request.user).prefetch_related('photos')
    return render(request, 'inventory/my_listings.html', {'listings': listings})


@login_required(login_url='ui_preview:login')
def user_listing_detail(request, pk):
    listing = get_object_or_404(
        RentalListing.objects.select_related(
            'owner',
            'owner__toolshare_profile',
        ).annotate(
            review_count=Count('reviews'),
            avg_rating=Avg('reviews__rating'),
        ).prefetch_related(
            'photos',
            Prefetch(
                'booking_requests',
                queryset=_approved_rentals(),
                to_attr='active_approved_bookings',
            ),
            Prefetch(
                'reviews',
                queryset=RentalReview.objects.select_related(
                    'reviewer',
                    'reviewer__toolshare_profile',
                ),
                to_attr='listing_reviews',
            ),
        ),
        pk=pk,
    )
    item = _listing_as_item(listing)
    form = RentalRequestForm(request.POST or None)
    review = RentalReview.objects.filter(
        listing=listing,
        reviewer=request.user,
    ).first()
    review_form = RentalReviewForm(instance=review)
    if request.method == 'POST':
        response = _submit_rental_request(request, item, form, listing=listing)
        if response:
            return response

    return render(request, 'inventory/item_detail.html', {
        'item': item,
        'booking_form': form,
        'review_form': review_form,
        'reviews': [
            {
                'author': review.reviewer.get_full_name() or review.reviewer.username,
                'avatar_url': _user_avatar_url(review.reviewer),
                'rating': review.rating,
                'date': review.created_at,
                'text': review.comment,
            }
            for review in listing.listing_reviews
        ],
        'review_url': reverse('ui_preview:submit_listing_review', args=[listing.pk]),
        'user_review': review,
        'booking_url': reverse('ui_preview:user_listing_detail', args=[listing.pk]),
        'can_book': listing.owner_id != request.user.id,
    })


@login_required(login_url='ui_preview:login')
@require_POST
def submit_listing_review(request, pk):
    listing = get_object_or_404(RentalListing, pk=pk)
    if listing.owner_id == request.user.id:
        messages.error(request, 'You cannot review your own listing.')
        return redirect('ui_preview:user_listing_detail', pk=listing.pk)

    review = RentalReview.objects.filter(
        listing=listing,
        reviewer=request.user,
    ).first()
    if review is None:
        review = RentalReview(listing=listing, reviewer=request.user)
    form = RentalReviewForm(request.POST, instance=review)
    if form.is_valid():
        form.save()
        messages.success(request, 'Your review has been saved.')
    else:
        for error in form.errors.get('rating', []):
            messages.error(request, error)
        for error in form.errors.get('comment', []):
            messages.error(request, error)
        if form.non_field_errors():
            messages.error(request, 'Please correct the review and try again.')
    return redirect(f"{reverse('ui_preview:user_listing_detail', args=[listing.pk])}#reviews")


@login_required(login_url='ui_preview:login')
def my_rentals(request):
    rentals = RentalBooking.objects.filter(renter=request.user)
    return render(request, 'inventory/my_rentals.html', {
        'rentals': rentals,
        'today': timezone.localdate(),
    })


@login_required(login_url='ui_preview:login')
@require_POST
def cancel_rental(request, booking_id):
    rental = get_object_or_404(
        RentalBooking,
        pk=booking_id,
        renter=request.user,
    )
    if rental.status not in (
        RentalBooking.Status.REQUESTED,
        RentalBooking.Status.APPROVED,
    ) or rental.start_date < timezone.localdate():
        messages.error(request, 'This rental can no longer be cancelled.')
        return redirect('ui_preview:my_rentals')

    rental.status = RentalBooking.Status.CANCELLED
    rental.save(update_fields=['status'])
    messages.success(request, f"Your request for '{rental.item_title}' has been cancelled.")
    return redirect('ui_preview:my_rentals')


@login_required(login_url='ui_preview:login')
@require_POST
def delete_rental(request, booking_id):
    rental = get_object_or_404(
        RentalBooking,
        pk=booking_id,
        renter=request.user,
    )
    item_title = rental.item_title
    rental.delete()
    messages.success(request, f"Booking for '{item_title}' was permanently deleted.")
    return redirect('ui_preview:my_rentals')


@login_required(login_url='ui_preview:login')
def rental_notifications(request):
    requests = RentalBooking.objects.filter(
        listing__owner=request.user,
    ).select_related('renter', 'listing')
    availability_notifications = list(
        request.user.rental_availability_notifications.select_related(
            'booking',
            'booking__listing',
        )
    )
    request.user.rental_availability_notifications.filter(
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    return render(request, 'inventory/rental_notifications.html', {
        'rental_requests': requests,
        'pending_count': requests.filter(status=RentalBooking.Status.REQUESTED).count(),
        'availability_notifications': availability_notifications,
        'unread_availability_notifications': 0,
    })


@login_required(login_url='ui_preview:login')
@require_POST
def respond_to_rental_request(request, booking_id, action):
    rental_request = get_object_or_404(
        RentalBooking.objects.select_related('listing'),
        pk=booking_id,
        listing__owner=request.user,
    )
    if rental_request.status != RentalBooking.Status.REQUESTED:
        messages.error(request, 'This rental request has already been handled.')
        return redirect('ui_preview:notifications')

    if action == 'approve':
        if _has_booking_conflict(
            rental_request.listing,
            rental_request.start_date,
            rental_request.end_date,
            exclude_booking_id=rental_request.pk,
        ):
            messages.error(
                request,
                'This request overlaps another active rental. Reject it or resolve the conflicting request before approving.',
            )
            return redirect('ui_preview:notifications')
        rental_request.status = RentalBooking.Status.APPROVED
        message = f"Approved the request for '{rental_request.item_title}'."
    elif action == 'reject':
        rental_request.status = RentalBooking.Status.REJECTED
        message = f"Rejected the request for '{rental_request.item_title}'."
    else:
        messages.error(request, 'Invalid action for rental request.')
        return redirect('ui_preview:notifications')

    rental_request.save(update_fields=['status'])
    messages.success(request, message)
    return redirect('ui_preview:notifications')


@login_required(login_url='ui_preview:login')
def user_settings(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ThemeSettingsForm(request.POST or None, instance=user_profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your appearance settings have been saved.')
        return redirect('ui_preview:settings')
    return render(request, 'accounts/settings.html', {'form': form, 'profile': user_profile})


def _listing_as_item(listing):
    owner_name = listing.owner.get_full_name() or listing.owner.username
    try:
        owner_profile = listing.owner.toolshare_profile
    except UserProfile.DoesNotExist:
        owner_profile = None
    phone_number = owner_profile.phone_number if owner_profile else ''
    whatsapp_phone = re.sub(r'\D', '', phone_number)
    call_phone = re.sub(r'[^\d+]', '', phone_number)
    approved_rentals = getattr(listing, 'active_approved_bookings', [])
    active_rental = approved_rentals[0] if approved_rentals else None
    photos = list(listing.photos.all())
    return {
        'pk': listing.pk,
        'owner_id': listing.owner_id,
        'title': listing.title,
        'city': listing.city,
        'daily_price': listing.daily_price,
        'security_deposit': listing.security_deposit,
        'category': {'name': listing.category},
        'avg_rating': listing.avg_rating or 0,
        'review_count': listing.review_count,
        'description': listing.description,
        'owner': owner_name,
        'owner_avatar_url': _user_avatar_url(listing.owner),
        'contact_phone': call_phone,
        'whatsapp_phone': whatsapp_phone,
        'whatsapp_message': (
            f"Hello, I am interested in your {listing.title}. "
            'Could you tell me a bit more about it?'
        ),
        'rented_start_date': active_rental.start_date if active_rental else None,
        'rented_end_date': active_rental.end_date if active_rental else None,
        'brand': listing.brand or 'Not specified',
        'condition': 'Not specified',
        'image_url': listing.image_url,
        'image': listing.image,
        'photos': photos,
        'detail_url': reverse('ui_preview:user_listing_detail', args=[listing.pk]),
    }


def _user_avatar_url(user):
    try:
        avatar_image = user.toolshare_profile.avatar_image
    except UserProfile.DoesNotExist:
        return ''
    return avatar_image.url if avatar_image else ''


def _listing_category_suggestions():
    saved_categories = RentalListing.objects.values_list(
        'category',
        flat=True,
    ).distinct()
    return sorted({
        label for value, label in LISTING_CATEGORIES
    } | set(saved_categories), key=str.casefold)


def _approved_rentals():
    return RentalBooking.objects.filter(
        status=RentalBooking.Status.APPROVED,
        end_date__gte=timezone.localdate(),
    ).order_by('start_date', 'end_date')


def _submit_rental_request(request, item, form, listing=None):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('ui_preview:login')}?next={request.path}")
    if listing is None:
        messages.error(request, 'This sample item is not connected to a lender and cannot be booked.')
        return redirect(request.path)
    if listing and listing.owner_id == request.user.id:
        messages.error(request, 'You cannot request to rent your own listing.')
        return redirect('ui_preview:my_listings')
    if not form.is_valid():
        return None

    start_date = form.cleaned_data['start_date']
    end_date = form.cleaned_data['end_date']
    if _has_booking_conflict(listing, start_date, end_date):
        available_from = _next_available_start_date(listing, start_date, end_date)
        form.add_error(
            None,
            f'This tool is already reserved for those dates. '
            f'The earliest available {((end_date - start_date).days + 1)}-day rental '
            f'starts on {date_format(available_from, "F j, Y")}.',
        )
        return None

    total_days = (end_date - start_date).days + 1
    primary_photo = item['photos'][0] if item['photos'] else None
    image_storage_name = (
        primary_photo.image.name
        if primary_photo
        else listing.image.name
        if listing.image
        else ''
    )
    image_url = '' if image_storage_name else item.get('image_url', '')
    RentalBooking.objects.create(
        renter=request.user,
        listing=listing,
        item_title=item['title'],
        item_category=item['category']['name'],
        item_city=item['city'],
        daily_price=item['daily_price'],
        security_deposit=item['security_deposit'],
        image_url=image_url,
        image_storage_name=image_storage_name,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
    )
    messages.success(request, f"Rental request for '{item['title']}' has been submitted successfully!")
    return redirect('ui_preview:my_rentals')


def _active_booking_queryset(listing):
    return RentalBooking.objects.filter(
        listing=listing,
        status__in=[
            RentalBooking.Status.REQUESTED,
            RentalBooking.Status.APPROVED,
        ],
    )


def _has_booking_conflict(listing, start_date, end_date, exclude_booking_id=None):
    conflicts = _active_booking_queryset(listing).filter(
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_booking_id is not None:
        conflicts = conflicts.exclude(pk=exclude_booking_id)
    return conflicts.exists()


def _next_available_start_date(listing, start_date, end_date):
    rental_days = (end_date - start_date).days + 1
    candidate = start_date
    reservations = _active_booking_queryset(listing).filter(
        end_date__gte=start_date,
    ).order_by('start_date', 'end_date')

    for reservation in reservations:
        if reservation.start_date > candidate:
            gap_days = (reservation.start_date - candidate).days
            if gap_days >= rental_days:
                return candidate
        if reservation.end_date >= candidate:
            candidate = reservation.end_date + timedelta(days=1)

    return candidate


def preview_review_form(request):
    return render(request, 'reviews/review_form.html', {'item': ITEMS[0]})


def preview_staff_index(request):
    return render(request, 'staff/index.html', {'user_count': 128, 'item_count': 64, 'booking_count': 312, 'pending_count': 7})


def preview_staff_user_list(request):
    return render(request, 'staff/user_list.html', {
        'users': [
            {'name': 'Aarav Kulkarni', 'email': 'aarav@example.com', 'joined': '14 Jan 2025', 'rentals': 12, 'status': 'Active'},
            {'name': 'Meera Shah', 'email': 'meera@example.com', 'joined': '02 Mar 2025', 'rentals': 8, 'status': 'Active'},
            {'name': 'Rohan Desai', 'email': 'rohan@example.com', 'joined': '19 Jun 2025', 'rentals': 3, 'status': 'Active'},
        ],
    })


def preview_staff_item_list(request):
    return render(request, 'staff/item_list.html', {'items': ITEMS})
