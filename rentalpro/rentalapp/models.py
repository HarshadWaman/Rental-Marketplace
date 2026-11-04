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


class PasswordResetOTP(models.Model):
    """Model to store OTP for password reset with expiration time."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
    )
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Password Reset OTP'
        verbose_name_plural = 'Password Reset OTPs'
    
    def __str__(self):
        return f'OTP for {self.user.username} - {self.otp}'
    
    @classmethod
    def generate_otp(cls):
        """Generate a random 6-digit OTP."""
        import random
        import string
        return ''.join(random.choices(string.digits, k=6))
    
    @classmethod
    def create_otp(cls, user, expiry_minutes=2, ip_address=None):
        """Create a new OTP for the user."""
        from django.utils import timezone
        otp_code = cls.generate_otp()
        expires_at = timezone.now() + timezone.timedelta(minutes=expiry_minutes)
        
        return cls.objects.create(
            user=user,
            otp=otp_code,
            expires_at=expires_at,
            ip_address=ip_address
        )
    
    def is_valid(self):
        """Check if the OTP is still valid (not expired and not used)."""
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at
    
    def mark_as_used(self):
        """Mark the OTP as used."""
        self.is_used = True
        self.save(update_fields=['is_used'])
    
    def time_remaining(self):
        """Get the remaining time in seconds until expiration."""
        from django.utils import timezone
        if not self.is_valid():
            return 0
        remaining = (self.expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining))


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
