from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import (
    RentalBooking,
    RentalListing,
    RentalListingPhoto,
    RentalReview,
    UserProfile,
)

admin.site.unregister(get_user_model())


@admin.register(get_user_model())
class RentalMarketplaceUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Password reset', {'fields': ('password_reset_link',)}),
    )
    readonly_fields = UserAdmin.readonly_fields + ('password_reset_link',)

    @admin.display(description='Reset this user’s password')
    def password_reset_link(self, obj):
        url = reverse(
            f'admin:{obj._meta.app_label}_{obj._meta.model_name}_password_change',
            args=[obj.pk],
        )
        return format_html('<a class="button" href="{}">Change password</a>', url)


@admin.register(RentalBooking)
class RentalBookingAdmin(ModelAdmin):
    list_display = ('item_title', 'renter', 'listing', 'start_date', 'end_date', 'total_days', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'created_at')
    search_fields = ('item_title', 'renter__username', 'renter__email')


@admin.register(RentalListing)
class RentalListingAdmin(ModelAdmin):
    list_display = ('title', 'owner', 'category', 'city', 'daily_price', 'created_at')
    list_filter = ('category', 'city', 'created_at')
    search_fields = ('title', 'owner__username', 'city')


@admin.register(RentalReview)
class RentalReviewAdmin(ModelAdmin):
    list_display = ('listing', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('listing__title', 'reviewer__username', 'comment')


@admin.register(RentalListingPhoto)
class RentalListingPhotoAdmin(ModelAdmin):
    list_display = ('listing', 'id')
    search_fields = ('listing__title', 'listing__owner__username')


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ('user', 'theme')
    search_fields = ('user__username', 'user__email')
