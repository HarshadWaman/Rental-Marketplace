from django.contrib import admin

from .models import RentalBooking, RentalListing, RentalReview, UserProfile


@admin.register(RentalBooking)
class RentalBookingAdmin(admin.ModelAdmin):
    list_display = ('item_title', 'renter', 'listing', 'start_date', 'end_date', 'total_days', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'created_at')
    search_fields = ('item_title', 'renter__username', 'renter__email')


@admin.register(RentalListing)
class RentalListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'city', 'daily_price', 'created_at')
    list_filter = ('category', 'city', 'created_at')
    search_fields = ('title', 'owner__username', 'city')


@admin.register(RentalReview)
class RentalReviewAdmin(admin.ModelAdmin):
    list_display = ('listing', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('listing__title', 'reviewer__username', 'comment')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme')
    search_fields = ('user__username', 'user__email')
