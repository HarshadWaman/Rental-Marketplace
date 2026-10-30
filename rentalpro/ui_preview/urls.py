from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView

from . import views

app_name = 'ui_preview'

urlpatterns = [
    path('', views.preview_item_list, name='item_list'),
    path('item/<int:pk>/', views.preview_item_detail, name='item_detail'),
    path('dashboard/', views.preview_dashboard, name='dashboard'),
    path('item/new/', views.preview_item_form, name='item_create'),
    path('listing/<int:pk>/edit/', views.edit_listing, name='edit_listing'),
    path('listing/<int:pk>/delete/', views.delete_listing, name='delete_listing'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('my-rentals/', views.my_rentals, name='my_rentals'),
    path('notifications/', views.rental_notifications, name='notifications'),
    path('notifications/<int:booking_id>/<str:action>/', views.respond_to_rental_request, name='respond_to_rental_request'),
    path('register/', views.preview_register, name='register'),
    path('login/', LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('ui_preview:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('ui_preview:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', views.preview_profile, name='profile'),
    path('settings/', views.user_settings, name='settings'),
    path('listing/<int:pk>/', views.user_listing_detail, name='user_listing_detail'),
    path('listing/<int:pk>/review/', views.submit_listing_review, name='submit_listing_review'),
    path('review/', views.preview_review_form, name='review_form'),
    path('staff/', views.preview_staff_index, name='staff_index'),
    path('staff/users/', views.preview_staff_user_list, name='staff_user_list'),
    path('staff/items/', views.preview_staff_item_list, name='staff_item_list'),
]
