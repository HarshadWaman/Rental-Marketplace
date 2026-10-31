from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models


class UserProfile(models.Model):
    class Theme(models.TextChoices):
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='toolshare_profile',
    )
    avatar_image = models.ImageField(upload_to='profiles/', blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    theme = models.CharField(max_length=5, choices=Theme.choices, default=Theme.LIGHT)

    def __str__(self):
        return f'{self.user.username} profile'


class RentalListing(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_listings',
    )
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=80)
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    daily_price = models.DecimalField(max_digits=9, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    image_url = models.URLField(blank=True)
    image = models.ImageField(upload_to='listings/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class RentalListingPhoto(models.Model):
    listing = models.ForeignKey(
        RentalListing,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    image = models.ImageField(upload_to='listings/')

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f'Photo for {self.listing.title}'


class RentalReview(models.Model):
    listing = models.ForeignKey(
        RentalListing,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_reviews',
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['listing', 'reviewer'],
                name='unique_rental_review_per_user',
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name='rental_review_rating_between_1_and_5',
            ),
        ]

    def __str__(self):
        return f'{self.rating}/5 review for {self.listing.title}'


class RentalBooking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_bookings',
    )
    listing = models.ForeignKey(
        RentalListing,
        on_delete=models.SET_NULL,
        related_name='booking_requests',
        null=True,
        blank=True,
    )
    item_title = models.CharField(max_length=120)
    item_category = models.CharField(max_length=80)
    item_city = models.CharField(max_length=100)
    daily_price = models.DecimalField(max_digits=9, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    image_url = models.URLField(blank=True)
    image_storage_name = models.CharField(max_length=500, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def total_price(self):
        return self.daily_price * self.total_days

    @property
    def total_due(self):
        return self.total_price + self.security_deposit

    @property
    def display_image_url(self):
        if self.image_storage_name:
            return default_storage.url(self.image_storage_name)
        if self.listing_id:
            photo = self.listing.photos.first()
            if photo:
                return photo.image.url
            if self.listing.image:
                return self.listing.image.url
        return self.image_url

    def __str__(self):
        return f'{self.item_title} requested by {self.renter.username}'


class RentalAvailabilityNotification(models.Model):
    booking = models.OneToOneField(
        RentalBooking,
        on_delete=models.CASCADE,
        related_name='availability_notification',
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_availability_notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.booking.item_title} is available for {self.renter.username}'
