import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from unfold.admin import ModelAdmin

from .admin import (
    RentalBookingAdmin,
    RentalListingAdmin,
    RentalMarketplaceUserAdmin,
    RentalReviewAdmin,
    UserProfileAdmin,
)


class EnsureRenderSuperuserTests(TestCase):
    def test_authenticated_admin_uses_unfold(self):
        user = get_user_model().objects.create_superuser(
            username='admin-ui-test',
            email='admin-ui-test@example.com',
            password='Safe-password-983!',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rental Marketplace')
        self.assertContains(response, 'unfold')
        for model_admin in (
            RentalBookingAdmin,
            RentalListingAdmin,
            RentalReviewAdmin,
            UserProfileAdmin,
        ):
            self.assertTrue(issubclass(model_admin, ModelAdmin))
        self.assertTrue(issubclass(RentalMarketplaceUserAdmin, UserAdmin))

    def test_user_admin_has_visible_password_reset_action(self):
        admin_user = get_user_model().objects.create_superuser(
            username='password-admin',
            email='password-admin@example.com',
            password='Safe-password-983!',
        )
        user = get_user_model().objects.create_user(
            username='password-target',
            email='password-target@example.com',
            password='Original-password-983!',
        )
        self.client.force_login(admin_user)

        change_url = reverse('admin:auth_user_change', args=[user.pk])
        response = self.client.get(change_url)

        self.assertEqual(response.status_code, 200)
        password_url = reverse('admin:auth_user_password_change', args=[user.pk])
        self.assertContains(response, 'Password reset')
        self.assertContains(response, 'Change password')
        self.assertContains(response, password_url)

        password_response = self.client.get(password_url)
        self.assertEqual(password_response.status_code, 200)
        self.assertContains(password_response, 'Change password')

        password_response = self.client.post(password_url, {
            'password1': 'Changed-password-984!',
            'password2': 'Changed-password-984!',
        })
        self.assertEqual(password_response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password('Changed-password-984!'))

    def test_skips_when_environment_variables_are_not_configured(self):
        variables = {
            'DJANGO_SUPERUSER_USERNAME': '',
            'DJANGO_SUPERUSER_EMAIL': '',
            'DJANGO_SUPERUSER_PASSWORD': '',
        }
        with patch.dict(os.environ, variables):
            call_command('ensure_render_superuser')

        self.assertFalse(get_user_model().objects.exists())

    def test_requires_all_environment_variables_when_partially_configured(self):
        variables = {
            'DJANGO_SUPERUSER_USERNAME': 'render-admin',
            'DJANGO_SUPERUSER_EMAIL': 'admin@example.com',
            'DJANGO_SUPERUSER_PASSWORD': '',
        }
        with patch.dict(os.environ, variables):
            with self.assertRaisesMessage(CommandError, 'DJANGO_SUPERUSER_PASSWORD'):
                call_command('ensure_render_superuser')

    def test_creates_superuser_from_environment_variables(self):
        variables = {
            'DJANGO_SUPERUSER_USERNAME': 'render-admin',
            'DJANGO_SUPERUSER_EMAIL': 'admin@example.com',
            'DJANGO_SUPERUSER_PASSWORD': 'Safe-password-983!',
        }
        with patch.dict(os.environ, variables):
            call_command('ensure_render_superuser')

        user = get_user_model().objects.get(username='render-admin')
        self.assertEqual(user.email, 'admin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('Safe-password-983!'))

    def test_leaves_existing_superuser_and_password_unchanged(self):
        user_model = get_user_model()
        user = user_model.objects.create_superuser(
            username='render-admin',
            email='old@example.com',
            password='Original-password-983!',
        )
        variables = {
            'DJANGO_SUPERUSER_USERNAME': 'render-admin',
            'DJANGO_SUPERUSER_EMAIL': 'admin@example.com',
            'DJANGO_SUPERUSER_PASSWORD': 'New-password-983!',
        }

        with patch.dict(os.environ, variables):
            call_command('ensure_render_superuser')

        user.refresh_from_db()
        self.assertEqual(user.email, 'old@example.com')
        self.assertTrue(user.check_password('Original-password-983!'))
