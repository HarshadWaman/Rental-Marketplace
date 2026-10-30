from io import BytesIO
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.template.loader import get_template
from django.utils import timezone
from PIL import Image

from rentalapp.models import (
    RentalAvailabilityNotification,
    RentalBooking,
    RentalListing,
    RentalReview,
    UserProfile,
)


class PreviewPageTests(TestCase):
    def test_homepage_renders_catalog(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tools ready to rent')
        self.assertContains(response, 'Good tools deserve to be used.')
        self.assertContains(response, 'Marketplace</h2>')
        self.assertContains(response, 'Create an account')
        self.assertNotContains(response, 'Preview only')
        self.assertNotContains(response, 'My dashboard')
        self.assertNotContains(response, 'Staff preview')
        self.assertNotContains(response, 'Admin panel')

    def test_admin_panel_is_not_linked_from_homepage(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Admin panel')

    def test_django_admin_remains_available_by_url(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_all_preview_pages_render(self):
        pages = [
            ('ui_preview:item_list', None),
            ('ui_preview:item_detail', [1]),
            ('ui_preview:dashboard', None),
            ('ui_preview:register', None),
            ('ui_preview:login', None),
            ('ui_preview:password_reset', None),
            ('ui_preview:password_reset_done', None),
            ('ui_preview:password_reset_complete', None),
            ('ui_preview:review_form', None),
            ('ui_preview:staff_index', None),
            ('ui_preview:staff_user_list', None),
            ('ui_preview:staff_item_list', None),
        ]

        for route_name, args in pages:
            with self.subTest(page=route_name):
                response = self.client.get(reverse(route_name, args=args))
                self.assertEqual(response.status_code, 200)

    def test_registration_creates_user_profile_and_signs_user_in(self):
        response = self.client.post(reverse('ui_preview:register'), {
            'username': 'new-renter',
            'first_name': 'Nina',
            'last_name': 'Shah',
            'email': 'nina@example.com',
            'phone_number': '+91 98765 43210',
            'password1': 'Safe-password-983!',
            'password2': 'Safe-password-983!',
        })

        self.assertRedirects(response, reverse('ui_preview:item_list'))
        user = get_user_model().objects.get(username='new-renter')
        self.assertEqual(user.get_full_name(), 'Nina Shah')
        self.assertEqual(user.email, 'nina@example.com')
        self.assertEqual(user.toolshare_profile.phone_number, '+91 98765 43210')
        self.assertTrue(user.check_password('Safe-password-983!'))
        self.assertTrue(self.client.get('/').wsgi_request.user.is_authenticated)
        self.assertTrue(hasattr(user, 'toolshare_profile'))

    def test_registration_shows_password_validation_errors(self):
        response = self.client.post(reverse('ui_preview:register'), {
            'username': 'new-renter',
            'first_name': 'Nina',
            'last_name': 'Shah',
            'email': 'nina@example.com',
            'phone_number': '+91 98765 43210',
            'password1': 'short',
            'password2': 'different',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The two password fields didn’t match.')
        self.assertFalse(get_user_model().objects.filter(username='new-renter').exists())

    def test_registration_rejects_invalid_phone_number(self):
        response = self.client.post(reverse('ui_preview:register'), {
            'username': 'bad-phone-user',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test-phone@example.com',
            'phone_number': 'phone-number',
            'password1': 'Safe-password-983!',
            'password2': 'Safe-password-983!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid phone number.')
        self.assertFalse(get_user_model().objects.filter(username='bad-phone-user').exists())

    def test_password_visibility_controls_render_on_auth_forms(self):
        registration_response = self.client.get(reverse('ui_preview:register'))
        self.assertContains(registration_response, 'data-toggle-password', count=2)

        login_response = self.client.get(reverse('ui_preview:login'))
        self.assertContains(login_response, 'data-toggle-password')

        user = get_user_model().objects.create_user(
            username='visibility-user',
            email='visibility@example.com',
            password='safe-test-password',
        )
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            self.client.post(
                reverse('ui_preview:password_reset'),
                {'email': user.email},
            )
            reset_url = next(
                line for line in mail.outbox[0].body.splitlines()
                if line.startswith('http://')
            )
            confirm_response = self.client.get(reset_url, follow=True)

        self.assertContains(confirm_response, 'data-toggle-password', count=2)

    def test_listing_form_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse('ui_preview:item_create'))

        self.assertRedirects(
            response,
            f"{reverse('ui_preview:login')}?next={reverse('ui_preview:item_create')}",
        )

    def test_authenticated_user_can_open_listing_form(self):
        user = get_user_model().objects.create_user(username='renter', password='safe-test-password')
        self.client.force_login(user)

        response = self.client.get(reverse('ui_preview:item_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List a tool for rent')

    def test_listing_form_supports_camera_and_browsed_image_upload(self):
        user = get_user_model().objects.create_user(
            username='image-uploader',
            password='safe-test-password',
        )
        self.client.force_login(user)
        form_response = self.client.get(reverse('ui_preview:item_create'))
        self.assertContains(form_response, 'Take a photo')
        self.assertContains(form_response, 'Browse files')
        self.assertContains(form_response, 'enctype="multipart/form-data"')
        self.assertContains(form_response, 'accept="image/*"')
        self.assertContains(form_response, 'capture="environment"')
        self.assertNotContains(form_response, 'Tool photo URL')

        image_buffer = BytesIO()
        Image.new('RGB', (1, 1), color='green').save(image_buffer, format='PNG')
        uploaded_image = SimpleUploadedFile(
            'tool.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )

        with tempfile.TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                response = self.client.post(
                    reverse('ui_preview:item_create'),
                    {
                        'title': 'Uploaded Image Drill',
                        'category': 'Power tools',
                        'description': 'A drill with an uploaded photo.',
                        'city': 'Pune',
                        'daily_price': '250',
                        'security_deposit': '800',
                        'image': uploaded_image,
                    },
                )

                self.assertRedirects(response, reverse('ui_preview:my_listings'))
                listing = RentalListing.objects.get(title='Uploaded Image Drill')
                self.assertEqual(listing.image.name, 'listings/tool.png')
                self.assertTrue(listing.image.storage.exists(listing.image.name))
                catalog_response = self.client.get(reverse('ui_preview:item_list'))
                self.assertContains(catalog_response, '/media/listings/tool.png')
                self.client.force_login(user)
                detail_response = self.client.get(
                    reverse('ui_preview:user_listing_detail', args=[listing.pk])
                )
                self.assertContains(detail_response, '/media/listings/tool.png')

    def test_profile_settings_and_my_listings_require_login(self):
        for route_name in (
            'ui_preview:profile',
            'ui_preview:settings',
            'ui_preview:my_listings',
            'ui_preview:my_rentals',
            'ui_preview:notifications',
        ):
            with self.subTest(page=route_name):
                response = self.client.get(reverse(route_name))
                self.assertRedirects(
                    response,
                    f"{reverse('ui_preview:login')}?next={reverse(route_name)}",
                )

    def test_user_can_update_profile_and_avatar(self):
        user = get_user_model().objects.create_user(
            username='profile-user',
            password='safe-test-password',
        )
        self.client.force_login(user)
        image_buffer = BytesIO()
        Image.new('RGB', (1, 1), color='blue').save(image_buffer, format='PNG')
        uploaded_image = SimpleUploadedFile(
            'profile.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )

        with tempfile.TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                response = self.client.post(reverse('ui_preview:profile'), {
                    'first_name': 'Riya',
                    'last_name': 'Shah',
                    'email': 'riya@example.com',
                    'avatar_image': uploaded_image,
                })

                self.assertRedirects(response, reverse('ui_preview:profile'))
                user.toolshare_profile.refresh_from_db()
                self.assertEqual(user.toolshare_profile.avatar_image.name, 'profiles/profile.png')
                self.assertTrue(
                    user.toolshare_profile.avatar_image.storage.exists(
                        user.toolshare_profile.avatar_image.name
                    )
                )
                self.assertContains(
                    self.client.get(reverse('ui_preview:profile')),
                    '/media/profiles/profile.png',
                )
                self.assertContains(self.client.get('/'), '/media/profiles/profile.png')

        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), 'Riya Shah')
        self.assertEqual(user.email, 'riya@example.com')

    def test_profile_page_uses_browse_upload_instead_of_avatar_url(self):
        user = get_user_model().objects.create_user(
            username='profile-upload-page',
            password='safe-test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('ui_preview:profile'))

        self.assertContains(response, 'Profile picture')
        self.assertContains(response, 'type="file"')
        self.assertContains(response, 'accept="image/*"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, 'Profile picture URL')

    def test_profile_and_settings_pages_show_saved_account_details(self):
        user = get_user_model().objects.create_user(
            username='page-user',
            first_name='Dev',
            last_name='Patel',
            email='dev@example.com',
            password='safe-test-password',
        )
        self.client.force_login(user)

        profile_response = self.client.get(reverse('ui_preview:profile'))
        self.assertContains(profile_response, 'Dev Patel')
        self.assertContains(profile_response, 'dev@example.com')

        settings_response = self.client.get(reverse('ui_preview:settings'))
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(settings_response, 'data-theme-toggle')
        self.assertContains(settings_response, 'Light mode')

    def test_user_can_save_theme_preference(self):
        user = get_user_model().objects.create_user(
            username='theme-user',
            password='safe-test-password',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('ui_preview:settings'), {'theme': 'dark'})

        self.assertRedirects(response, reverse('ui_preview:settings'))
        self.assertContains(self.client.get('/'), 'data-theme="dark"')

    def test_users_only_see_their_own_listings_on_my_listings_page(self):
        first_user = get_user_model().objects.create_user(
            username='first-owner',
            password='safe-test-password',
        )
        UserProfile.objects.create(user=first_user, phone_number='+91 98765 43210')
        self.client.force_login(first_user)
        response = self.client.post(reverse('ui_preview:item_create'), {
            'title': 'My Circular Saw',
            'category': 'Power tools',
            'description': 'A sharp, reliable saw.',
            'city': 'Pune',
            'daily_price': '250',
            'security_deposit': '800',
            'image_url': '',
        })

        self.assertRedirects(response, reverse('ui_preview:my_listings'))
        own_listings = self.client.get(reverse('ui_preview:my_listings'))
        self.assertContains(own_listings, 'My Circular Saw')
        marketplace = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(marketplace, 'My Circular Saw')
        self.assertContains(marketplace, reverse('ui_preview:user_listing_detail', args=[1]))
        self.assertNotContains(marketplace, 'WhatsApp')
        self.assertNotContains(marketplace, 'href="tel:+919876543210"')

        second_user = get_user_model().objects.create_user(
            username='second-owner',
            password='safe-test-password',
        )
        self.client.force_login(second_user)
        other_user_catalog = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(other_user_catalog, 'WhatsApp')
        self.assertContains(other_user_catalog, 'href="tel:+919876543210"')
        other_listings = self.client.get(reverse('ui_preview:my_listings'))
        self.assertNotContains(other_listings, 'My Circular Saw')
        self.assertContains(other_listings, 'You haven’t listed any tools yet')

    def test_user_can_create_and_filter_a_custom_listing_category(self):
        user = get_user_model().objects.create_user(
            username='custom-category-owner',
            password='safe-test-password',
        )
        self.client.force_login(user)

        form_response = self.client.get(reverse('ui_preview:item_create'))
        self.assertContains(form_response, 'Choose a suggestion or type your own category.')
        self.assertContains(form_response, '<option value="Power tools">', html=False)

        response = self.client.post(reverse('ui_preview:item_create'), {
            'title': 'Custom Category Item',
            'category': 'Musical instruments',
            'description': 'A keyboard for rent.',
            'city': 'Pune',
            'daily_price': '400',
            'security_deposit': '1000',
        })

        self.assertRedirects(response, reverse('ui_preview:my_listings'))
        listing = RentalListing.objects.get(title='Custom Category Item')
        self.assertEqual(listing.category, 'Musical instruments')

        catalog_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(catalog_response, '<option value="Musical instruments">', html=False)
        filtered_response = self.client.get(
            reverse('ui_preview:item_list'),
            {'category': 'Musical instruments'},
        )
        self.assertContains(filtered_response, 'Custom Category Item')
        self.assertNotContains(filtered_response, 'My Circular Saw')

        edit_response = self.client.get(
            reverse('ui_preview:edit_listing', args=[listing.pk])
        )
        self.assertContains(edit_response, 'value="Musical instruments"')

    def test_listing_owner_can_edit_listing_and_other_users_cannot(self):
        owner = get_user_model().objects.create_user(
            username='edit-listing-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=owner,
            title='Original Listing Title',
            category='Power tools',
            description='Original description.',
            city='Pune',
            daily_price='250.00',
            security_deposit='800.00',
        )
        edit_url = reverse('ui_preview:edit_listing', args=[listing.pk])
        self.client.force_login(owner)

        owner_catalog = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(owner_catalog, edit_url)
        edit_form = self.client.get(edit_url)
        self.assertEqual(edit_form.status_code, 200)
        self.assertContains(edit_form, 'Edit your listing')
        self.assertContains(edit_form, 'value="Original Listing Title"')

        response = self.client.post(edit_url, {
            'title': 'Updated Listing Title',
            'category': 'Power tools',
            'description': 'Updated description.',
            'city': 'Mumbai',
            'daily_price': '300',
            'security_deposit': '900',
        })

        self.assertRedirects(response, reverse('ui_preview:my_listings'))
        listing.refresh_from_db()
        self.assertEqual(listing.title, 'Updated Listing Title')
        self.assertEqual(listing.description, 'Updated description.')
        self.assertEqual(listing.city, 'Mumbai')
        self.assertEqual(listing.daily_price, 300)
        self.assertEqual(listing.security_deposit, 900)

        other_user = get_user_model().objects.create_user(
            username='edit-listing-other',
            password='safe-test-password',
        )
        self.client.force_login(other_user)
        other_catalog = self.client.get(reverse('ui_preview:item_list'))
        self.assertNotContains(other_catalog, edit_url)
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(
            self.client.post(edit_url, {
                'title': 'Unauthorized Change',
                'category': 'Power tools',
                'description': '',
                'city': 'Pune',
                'daily_price': '1',
                'security_deposit': '0',
            }).status_code,
            404,
        )
        listing.refresh_from_db()
        self.assertEqual(listing.title, 'Updated Listing Title')

    def test_listing_owner_can_delete_listing_and_other_users_cannot(self):
        owner = get_user_model().objects.create_user(
            username='delete-listing-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=owner,
            title='Listing To Delete',
            category='Power tools',
            city='Pune',
            daily_price='250.00',
        )
        delete_url = reverse('ui_preview:delete_listing', args=[listing.pk])
        self.client.force_login(owner)

        my_listings = self.client.get(reverse('ui_preview:my_listings'))
        self.assertContains(my_listings, 'aria-label="Delete Listing To Delete"')
        self.assertContains(my_listings, 'method="post"')

        other_user = get_user_model().objects.create_user(
            username='delete-listing-other',
            password='safe-test-password',
        )
        self.client.force_login(other_user)
        self.assertEqual(self.client.post(delete_url).status_code, 404)
        self.assertTrue(RentalListing.objects.filter(pk=listing.pk).exists())

        self.client.force_login(owner)
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 405)
        response = self.client.post(delete_url, follow=True)

        self.assertRedirects(response, reverse('ui_preview:my_listings'))
        self.assertFalse(RentalListing.objects.filter(pk=listing.pk).exists())

    def test_marketplace_listing_has_whatsapp_and_call_links_for_lender(self):
        owner = get_user_model().objects.create_user(
            username='contact-owner',
            password='safe-test-password',
        )
        UserProfile.objects.create(user=owner, phone_number='+91 98765 43210')
        listing = RentalListing.objects.create(
            owner=owner,
            title='Cordless Drill',
            category='Power tools',
            city='Pune',
            daily_price=350,
            security_deposit=1000,
        )

        catalog_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(catalog_response, 'Log in for WhatsApp')
        self.assertContains(catalog_response, 'Log in to call')
        self.assertNotContains(catalog_response, 'https://wa.me/')
        self.assertNotContains(catalog_response, 'tel:+919876543210')
        renter = get_user_model().objects.create_user(
            username='contact-renter',
            password='safe-test-password',
        )
        self.client.force_login(renter)
        detail_response = self.client.get(
            reverse('ui_preview:user_listing_detail', args=[listing.pk])
        )
        self.assertContains(
            detail_response,
            'href="https://wa.me/919876543210?text=Hello%2C',
        )
        self.assertContains(detail_response, 'interested%20in%20your%20Cordless%20Drill')
        self.assertContains(detail_response, 'Could%20you%20tell%20me%20a%20bit%20more')
        self.assertContains(detail_response, 'href="tel:+919876543210"')
        self.assertContains(detail_response, 'WhatsApp')
        self.assertContains(detail_response, 'Call')

    def test_guest_contact_actions_require_login_without_exposing_lender_phone(self):
        owner = get_user_model().objects.create_user(
            username='guest-contact-owner',
            password='safe-test-password',
        )
        UserProfile.objects.create(user=owner, phone_number='+91 98765 43210')
        listing = RentalListing.objects.create(
            owner=owner,
            title='Guest Contact Drill',
            category='Power tools',
            city='Pune',
            daily_price=350,
        )

        catalog_url = reverse('ui_preview:item_list')
        response = self.client.get(catalog_url)

        login_url = f"{reverse('ui_preview:login')}?next={catalog_url}"
        self.assertContains(response, f'href="{login_url}"')
        self.assertContains(response, 'Log in for WhatsApp')
        self.assertContains(response, 'Log in to call')
        self.assertNotContains(response, 'https://wa.me/')
        self.assertNotContains(response, 'tel:+919876543210')

        booking_response = self.client.get(
            reverse('ui_preview:user_listing_detail', args=[listing.pk])
        )
        self.assertRedirects(
            booking_response,
            f"{reverse('ui_preview:login')}?next={reverse('ui_preview:user_listing_detail', args=[listing.pk])}",
        )

    def test_marketplace_shows_dates_for_approved_rental_only(self):
        lender = get_user_model().objects.create_user(
            username='rented-item-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Currently Rented Saw',
            category='Power tools',
            city='Pune',
            daily_price='250.00',
        )
        renter = get_user_model().objects.create_user(
            username='rented-item-borrower',
            password='safe-test-password',
        )
        booking = RentalBooking.objects.create(
            renter=renter,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            start_date='2026-11-01',
            end_date='2026-11-05',
            total_days=5,
            status=RentalBooking.Status.REQUESTED,
        )

        pending_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertNotContains(pending_response, 'This item is rented for')

        booking.status = RentalBooking.Status.APPROVED
        booking.save(update_fields=['status'])
        catalog_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(
            catalog_response,
            'This item is rented for Nov 1, 2026 to Nov 5, 2026.',
        )
        self.client.force_login(renter)
        detail_response = self.client.get(
            reverse('ui_preview:user_listing_detail', args=[listing.pk])
        )
        self.assertContains(
            detail_response,
            'This item is rented for Nov 1, 2026 to Nov 5, 2026.',
        )

    def test_listing_images_can_open_in_fullscreen_viewer(self):
        lender = get_user_model().objects.create_user(
            username='lightbox-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Zoomable Listing Image',
            category='Power tools',
            city='Pune',
            daily_price='250.00',
            image_url='https://example.com/tool.png',
        )

        catalog_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(catalog_response, 'data-image-lightbox')
        self.assertContains(catalog_response, 'aria-label="View Zoomable Listing Image image full screen"')

        renter = get_user_model().objects.create_user(
            username='lightbox-renter',
            password='safe-test-password',
        )
        self.client.force_login(renter)
        detail_response = self.client.get(
            reverse('ui_preview:user_listing_detail', args=[listing.pk])
        )
        self.assertContains(detail_response, 'id="imageLightbox"')
        self.assertContains(detail_response, 'id="imageLightboxTitle"')
        self.assertContains(detail_response, 'data-image-lightbox')
        self.assertContains(detail_response, 'js/image-lightbox.js')

    def test_user_can_submit_review_and_other_users_can_see_it(self):
        lender = get_user_model().objects.create_user(
            username='review-listing-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Reviewable Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        reviewer = get_user_model().objects.create_user(
            username='tool-reviewer',
            first_name='Maya',
            last_name='Patel',
            password='safe-test-password',
        )
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('ui_preview:submit_listing_review', args=[listing.pk]),
            {'rating': '5', 'comment': 'Worked perfectly and was easy to use.'},
        )

        self.assertRedirects(
            response,
            f"{reverse('ui_preview:user_listing_detail', args=[listing.pk])}#reviews",
        )
        review = RentalReview.objects.get(listing=listing, reviewer=reviewer)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Worked perfectly and was easy to use.')
        catalog_response = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(catalog_response, 'Rated 5.0 out of 5')

        other_user = get_user_model().objects.create_user(
            username='review-reader',
            password='safe-test-password',
        )
        self.client.force_login(other_user)
        detail_response = self.client.get(
            reverse('ui_preview:user_listing_detail', args=[listing.pk])
        )
        self.assertContains(detail_response, 'Maya Patel')
        self.assertContains(detail_response, 'Worked perfectly and was easy to use.')
        self.assertContains(detail_response, 'Rated 5.0 out of 5')
        self.assertContains(detail_response, 'Write a review', status_code=200)

    def test_user_can_update_their_review_without_duplicate(self):
        lender = get_user_model().objects.create_user(
            username='review-update-owner',
            password='safe-test-password',
        )
        reviewer = get_user_model().objects.create_user(
            username='review-update-user',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Review Update Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        existing_review = RentalReview.objects.create(
            listing=listing,
            reviewer=reviewer,
            rating=3,
            comment='It was okay.',
        )
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('ui_preview:submit_listing_review', args=[listing.pk]),
            {'rating': '4', 'comment': 'Actually, it worked very well.'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(RentalReview.objects.filter(listing=listing).count(), 1)
        existing_review.refresh_from_db()
        self.assertEqual(existing_review.rating, 4)
        self.assertEqual(existing_review.comment, 'Actually, it worked very well.')

    def test_listing_owner_cannot_review_their_own_item(self):
        owner = get_user_model().objects.create_user(
            username='review-own-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=owner,
            title='Owner Review Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        self.client.force_login(owner)

        response = self.client.post(
            reverse('ui_preview:submit_listing_review', args=[listing.pk]),
            {'rating': '5', 'comment': 'My own item.'},
            follow=True,
        )

        self.assertContains(response, 'You cannot review your own listing.')
        self.assertFalse(RentalReview.objects.filter(listing=listing).exists())

    def test_login_redirects_to_listing_form_after_authentication(self):
        user = get_user_model().objects.create_user(username='renter', password='safe-test-password')

        response = self.client.post(
            reverse('ui_preview:login') + f"?next={reverse('ui_preview:item_create')}",
            {'username': user.username, 'password': 'safe-test-password'},
        )

        self.assertRedirects(response, reverse('ui_preview:item_create'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_password_reset_flow_sends_email_and_updates_password(self):
        user = get_user_model().objects.create_user(
            username='reset-user',
            email='reset@example.com',
            password='old-safe-password',
        )

        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                reverse('ui_preview:password_reset'),
                {'email': user.email},
            )

            self.assertRedirects(response, reverse('ui_preview:password_reset_done'))
            self.assertEqual(len(mail.outbox), 1)

            reset_url = next(
                line for line in mail.outbox[0].body.splitlines()
                if line.startswith('http://')
            )
            response = self.client.get(reset_url, follow=True)
            self.assertEqual(response.status_code, 200)
            confirm_url = response.request['PATH_INFO']

            response = self.client.post(confirm_url, {
                'new_password1': 'new-safe-password-456',
                'new_password2': 'new-safe-password-456',
            })

        self.assertRedirects(response, reverse('ui_preview:password_reset_complete'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('new-safe-password-456'))
        self.assertTrue(self.client.login(username='reset-user', password='new-safe-password-456'))

    def test_login_page_has_forgot_password_link(self):
        response = self.client.get(reverse('ui_preview:login'))

        self.assertContains(response, reverse('ui_preview:password_reset'))

    def test_password_reset_does_not_disclose_unknown_email(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                reverse('ui_preview:password_reset'),
                {'email': 'unknown@example.com'},
            )

        self.assertRedirects(response, reverse('ui_preview:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_catalog_shows_only_member_listings_and_search_filters_them(self):
        owner = get_user_model().objects.create_user(
            username='catalog-owner',
            password='safe-test-password',
        )
        RentalListing.objects.create(
            owner=owner,
            title='Member Impact Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        RentalListing.objects.create(
            owner=owner,
            title='Member Pressure Washer',
            category='Cleaning',
            city='Mumbai',
            daily_price='500.00',
        )

        catalog = self.client.get(reverse('ui_preview:item_list'))
        self.assertContains(catalog, 'Member Impact Drill')
        self.assertContains(catalog, 'Member Pressure Washer')
        self.assertNotContains(catalog, 'Cordless Impact Drill')
        self.assertNotContains(catalog, '>Pressure Washer<')
        self.assertNotContains(catalog, 'Professional Ladder')

        response = self.client.get(reverse('ui_preview:item_list'), {'q': 'drill'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Member Impact Drill')
        self.assertNotContains(response, 'Member Pressure Washer')

    def test_anonymous_user_sees_login_prompt_on_item_detail(self):
        response = self.client.get(reverse('ui_preview:item_detail', args=[1]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log in to rent')
        self.assertContains(response, 'Please log in to book or rent this tool.')
        self.assertNotContains(response, '<button type="submit" class="btn btn-primary w-100 btn-lg">Request to book</button>')

    def test_anonymous_user_booking_attempt_redirects_to_login(self):
        response = self.client.post(
            reverse('ui_preview:item_detail', args=[1]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-03'},
        )

        self.assertRedirects(
            response,
            f"{reverse('ui_preview:login')}?next={reverse('ui_preview:item_detail', args=[1])}",
        )

    def test_authenticated_user_can_view_booking_form_and_book_item(self):
        lender = get_user_model().objects.create_user(username='bookable-owner', password='safe-test-password')
        listing = RentalListing.objects.create(
            owner=lender,
            title='Bookable Cordless Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
            security_deposit='1500.00',
        )
        user = get_user_model().objects.create_user(username='renter2', password='safe-test-password')
        self.client.force_login(user)

        response = self.client.get(reverse('ui_preview:user_listing_detail', args=[listing.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Request to book')
        self.assertNotContains(response, 'Log in to rent')

        post_response = self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-03'},
            follow=True,
        )
        self.assertRedirects(post_response, reverse('ui_preview:my_rentals'))
        self.assertContains(post_response, 'Rental request for')
        self.assertContains(post_response, 'Bookable Cordless Drill')
        self.assertContains(post_response, 'Requested')

    def test_sample_item_cannot_create_unrouted_rental_request(self):
        renter = get_user_model().objects.create_user(
            username='sample-renter',
            password='safe-test-password',
        )
        self.client.force_login(renter)

        response = self.client.get(reverse('ui_preview:item_detail', args=[1]))
        self.assertContains(response, 'isn’t connected to a lender account')

        response = self.client.post(
            reverse('ui_preview:item_detail', args=[1]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-03'},
            follow=True,
        )
        self.assertContains(response, 'cannot be booked')
        self.assertFalse(renter.rental_bookings.exists())

    def test_my_rentals_shows_only_current_users_requests(self):
        lender = get_user_model().objects.create_user(
            username='rental-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Rental Request Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        first_user = get_user_model().objects.create_user(
            username='first-renter',
            password='safe-test-password',
        )
        self.client.force_login(first_user)
        self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-03'},
        )
        first_response = self.client.get(reverse('ui_preview:my_rentals'))
        self.assertContains(first_response, 'Rental Request Drill')
        self.assertContains(first_response, '3 days')

        second_user = get_user_model().objects.create_user(
            username='second-renter',
            password='safe-test-password',
        )
        self.client.force_login(second_user)
        second_response = self.client.get(reverse('ui_preview:my_rentals'))
        self.assertNotContains(second_response, 'Cordless Impact Drill')
        self.assertContains(second_response, 'No rental requests yet')

    def test_rental_request_rejects_end_date_before_start_date(self):
        lender = get_user_model().objects.create_user(
            username='date-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Date Validation Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        user = get_user_model().objects.create_user(
            username='date-renter',
            password='safe-test-password',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-03', 'end_date': '2026-11-01'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The end date must be on or after the start date.')
        self.assertFalse(user.rental_bookings.exists())

    def test_overlapping_rental_request_shows_next_available_dates(self):
        lender = get_user_model().objects.create_user(
            username='availability-owner',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Reserved Drill',
            category='Power tools',
            city='Pune',
            daily_price='350.00',
        )
        current_renter = get_user_model().objects.create_user(
            username='current-renter',
            password='safe-test-password',
        )
        RentalBooking.objects.create(
            renter=current_renter,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            start_date='2026-11-01',
            end_date='2026-11-05',
            total_days=5,
        )
        next_renter = get_user_model().objects.create_user(
            username='next-renter',
            password='safe-test-password',
        )
        self.client.force_login(next_renter)

        response = self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-03', 'end_date': '2026-11-04'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')
        self.assertContains(response, 'earliest available 2-day rental starts on November 6, 2026')
        self.assertEqual(next_renter.rental_bookings.count(), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_availability_notification_sends_one_email_and_shows_in_app(self):
        lender = get_user_model().objects.create_user(
            username='availability-notice-owner',
            password='safe-test-password',
        )
        renter = get_user_model().objects.create_user(
            username='availability-notice-renter',
            email='renter@example.com',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Available Circular Saw',
            category='Power tools',
            city='Pune',
            daily_price='250.00',
        )
        today = timezone.localdate()
        booking = RentalBooking.objects.create(
            renter=renter,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            start_date=today,
            end_date=today,
            total_days=1,
            status=RentalBooking.Status.APPROVED,
        )

        call_command('send_rental_availability_notifications')
        call_command('send_rental_availability_notifications')

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Available Circular Saw', mail.outbox[0].subject)
        notification = RentalAvailabilityNotification.objects.get(booking=booking)
        self.assertIsNotNone(notification.email_sent_at)
        self.client.force_login(renter)
        self.assertContains(self.client.get('/'), 'notification-count')

        notification_response = self.client.get(reverse('ui_preview:notifications'))
        self.assertContains(notification_response, 'Available Circular Saw is available for your rental.')
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertNotContains(self.client.get('/'), 'notification-count')

    def test_lender_sees_and_can_approve_incoming_request(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(username='lender', password='safe-test-password')
        borrower = user_model.objects.create_user(
            username='borrower',
            first_name='Ravi',
            last_name='Kumar',
            email='ravi@example.com',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Lender Circular Saw',
            category='Power tools',
            description='Circular saw for rent.',
            city='Pune',
            daily_price='250.00',
            security_deposit='800.00',
        )
        self.client.force_login(borrower)
        self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-03'},
        )
        rental = RentalBooking.objects.get(renter=borrower, listing=listing)

        self.client.force_login(lender)
        notification_response = self.client.get(reverse('ui_preview:notifications'))
        self.assertContains(notification_response, 'Lender Circular Saw')
        self.assertContains(notification_response, 'Approve')
        self.assertContains(notification_response, 'Reject')
        self.assertContains(notification_response, '₹750')
        self.assertContains(notification_response, '₹800')
        self.assertContains(notification_response, '₹1550')
        self.assertContains(self.client.get('/'), 'notification-count')

        response = self.client.post(
            reverse('ui_preview:respond_to_rental_request', args=[rental.pk, 'approve']),
        )
        self.assertRedirects(response, reverse('ui_preview:notifications'))
        rental.refresh_from_db()
        self.assertEqual(rental.status, RentalBooking.Status.APPROVED)

        notification_response = self.client.get(reverse('ui_preview:notifications'))
        self.assertContains(notification_response, 'Ravi Kumar')
        self.assertContains(notification_response, 'ravi@example.com')
        self.assertNotContains(self.client.get('/'), 'notification-count')

        self.client.force_login(borrower)
        borrower_response = self.client.get(reverse('ui_preview:my_rentals'))
        self.assertContains(borrower_response, 'Your request has been accepted')
        self.assertContains(borrower_response, '₹1550')

    def test_lender_cannot_approve_conflicting_existing_rental_requests(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(
            username='conflict-owner',
            password='safe-test-password',
        )
        first_renter = user_model.objects.create_user(
            username='conflict-renter-one',
            password='safe-test-password',
        )
        second_renter = user_model.objects.create_user(
            username='conflict-renter-two',
            password='safe-test-password',
        )
        listing = RentalListing.objects.create(
            owner=lender,
            title='Conflict Check Saw',
            category='Power tools',
            city='Pune',
            daily_price='250.00',
        )
        first_request = RentalBooking.objects.create(
            renter=first_renter,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            start_date='2026-11-01',
            end_date='2026-11-03',
            total_days=3,
        )
        RentalBooking.objects.create(
            renter=second_renter,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            start_date='2026-11-02',
            end_date='2026-11-04',
            total_days=3,
        )
        self.client.force_login(lender)

        response = self.client.post(
            reverse(
                'ui_preview:respond_to_rental_request',
                args=[first_request.pk, 'approve'],
            ),
            follow=True,
        )

        self.assertContains(response, 'overlaps another active rental')
        first_request.refresh_from_db()
        self.assertEqual(first_request.status, RentalBooking.Status.REQUESTED)

    def test_only_the_listing_lender_sees_incoming_requests(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(username='request-owner', password='safe-test-password')
        other_lender = user_model.objects.create_user(username='other-owner', password='safe-test-password')
        borrower = user_model.objects.create_user(username='requester', password='safe-test-password')
        listing = RentalListing.objects.create(
            owner=lender,
            title='Private lender listing',
            category='Power tools',
            city='Pune',
            daily_price='100.00',
        )
        RentalBooking.objects.create(
            renter=borrower,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            security_deposit=listing.security_deposit,
            start_date='2026-11-01',
            end_date='2026-11-01',
            total_days=1,
        )

        self.client.force_login(other_lender)
        response = self.client.get(reverse('ui_preview:notifications'))

        self.assertContains(response, 'You’re all caught up')
        self.assertNotContains(response, 'Private lender listing')

    def test_notification_responses_require_post(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(username='method-owner', password='safe-test-password')
        borrower = user_model.objects.create_user(username='method-renter', password='safe-test-password')
        listing = RentalListing.objects.create(
            owner=lender,
            title='Method checked listing',
            category='Power tools',
            city='Pune',
            daily_price='100.00',
        )
        rental = RentalBooking.objects.create(
            renter=borrower,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            security_deposit=listing.security_deposit,
            start_date='2026-11-01',
            end_date='2026-11-01',
            total_days=1,
        )
        self.client.force_login(lender)

        response = self.client.get(
            reverse('ui_preview:respond_to_rental_request', args=[rental.pk, 'approve']),
        )

        self.assertEqual(response.status_code, 405)
        rental.refresh_from_db()
        self.assertEqual(rental.status, RentalBooking.Status.REQUESTED)

    def test_lender_can_reject_request_and_borrower_sees_declined_status(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(username='reject-lender', password='safe-test-password')
        borrower = user_model.objects.create_user(username='reject-borrower', password='safe-test-password')
        listing = RentalListing.objects.create(
            owner=lender,
            title='Lender Hedge Trimmer',
            category='Garden & outdoor',
            city='Pune',
            daily_price='100.00',
            security_deposit='200.00',
        )
        self.client.force_login(borrower)
        self.client.post(
            reverse('ui_preview:user_listing_detail', args=[listing.pk]),
            {'start_date': '2026-11-01', 'end_date': '2026-11-01'},
        )
        rental = RentalBooking.objects.get(renter=borrower, listing=listing)
        self.client.force_login(lender)

        response = self.client.post(
            reverse('ui_preview:respond_to_rental_request', args=[rental.pk, 'reject']),
        )

        self.assertRedirects(response, reverse('ui_preview:notifications'))
        rental.refresh_from_db()
        self.assertEqual(rental.status, RentalBooking.Status.REJECTED)
        self.client.force_login(borrower)
        self.assertContains(
            self.client.get(reverse('ui_preview:my_rentals')),
            'Your request was declined by the lender.',
        )

    def test_only_listing_owner_can_respond_to_request(self):
        user_model = get_user_model()
        lender = user_model.objects.create_user(username='real-lender', password='safe-test-password')
        other_user = user_model.objects.create_user(username='not-lender', password='safe-test-password')
        borrower = user_model.objects.create_user(username='request-borrower', password='safe-test-password')
        listing = RentalListing.objects.create(
            owner=lender,
            title='Owner-only Listing',
            category='Power tools',
            city='Pune',
            daily_price='100.00',
        )
        rental = RentalBooking.objects.create(
            renter=borrower,
            listing=listing,
            item_title=listing.title,
            item_category=listing.category,
            item_city=listing.city,
            daily_price=listing.daily_price,
            security_deposit=listing.security_deposit,
            start_date='2026-11-01',
            end_date='2026-11-01',
            total_days=1,
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse('ui_preview:respond_to_rental_request', args=[rental.pk, 'approve']),
        )

        self.assertEqual(response.status_code, 404)
        rental.refresh_from_db()
        self.assertEqual(rental.status, RentalBooking.Status.REQUESTED)

    def test_navbar_renders_auth_controls_correctly(self):
        # Anonymous user sees Log in and Join free
        anon_resp = self.client.get('/')
        self.assertContains(anon_resp, 'Log in')
        self.assertContains(anon_resp, 'Join free')
        self.assertNotContains(anon_resp, 'Log out')

        # Authenticated user sees username and Log out
        user = get_user_model().objects.create_user(username='navuser', password='safe-test-password')
        self.client.force_login(user)
        auth_resp = self.client.get('/')
        self.assertContains(auth_resp, 'navuser')
        self.assertContains(auth_resp, reverse('home:profile'))
        self.assertContains(auth_resp, reverse('home:my_listings'))
        self.assertContains(auth_resp, reverse('home:my_rentals'))
        self.assertContains(auth_resp, reverse('home:notifications'))
        self.assertContains(auth_resp, reverse('home:settings'))
        self.assertContains(auth_resp, 'Log out')
        self.assertNotContains(auth_resp, 'Join free')

    def test_shared_templates_compile(self):
        templates = [
            'base.html',
            'accounts/password_reset_form.html',
            'accounts/password_reset_done.html',
            'accounts/password_reset_confirm.html',
            'accounts/password_reset_complete.html',
            'accounts/password_reset_email.txt',
            'accounts/password_reset_subject.txt',
            'accounts/profile.html',
            'accounts/login.html',
            'accounts/register.html',
            'accounts/settings.html',
            'inventory/item_form.html',
            'inventory/my_listings.html',
            'inventory/my_rentals.html',
            'inventory/rental_notifications.html',
            'inventory/item_detail.html',
            'partials/_item_card.html',
            'partials/_rating_stars.html',
            'partials/_pagination.html',
            'partials/_booking_row.html',
            'partials/_form_field.html',
        ]

        for template_name in templates:
            with self.subTest(template=template_name):
                get_template(template_name)
