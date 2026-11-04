"""
Utility functions for the rental app.
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def send_simple_email(subject, message, recipient_list, from_email=None, fail_silently=False):
    """
    Send a simple text email.
    
    Args:
        subject (str): Email subject
        message (str): Email body (plain text)
        recipient_list (list): List of recipient email addresses
        from_email (str, optional): Sender email. Defaults to DEFAULT_FROM_EMAIL
        fail_silently (bool): If False, raise exceptions on error
    
    Returns:
        int: Number of successfully sent emails
    
    Example:
        send_simple_email(
            subject='Welcome to Rental Marketplace',
            message='Thank you for signing up!',
            recipient_list=['user@example.com']
        )
    """
    try:
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        return send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=fail_silently
        )
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        if not fail_silently:
            raise
        return 0


def send_html_email(subject, html_content, recipient_list, from_email=None, 
                    text_content=None, fail_silently=False):
    """
    Send an HTML email with optional plain text fallback.
    
    Args:
        subject (str): Email subject
        html_content (str): Email body in HTML format
        recipient_list (list): List of recipient email addresses
        from_email (str, optional): Sender email. Defaults to DEFAULT_FROM_EMAIL
        text_content (str, optional): Plain text version. Auto-generated if not provided
        fail_silently (bool): If False, raise exceptions on error
    
    Returns:
        int: Number of successfully sent emails
    """
    try:
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        
        # Auto-generate plain text version if not provided
        if text_content is None:
            text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=recipient_list
        )
        email.attach_alternative(html_content, "text/html")
        return email.send(fail_silently=fail_silently)
    except Exception as e:
        logger.error(f"Error sending HTML email: {e}")
        if not fail_silently:
            raise
        return 0



def send_template_email(subject, template_name, context, recipient_list, 
                       from_email=None, fail_silently=False):
    """
    Send an email using a Django template.
    
    Args:
        subject (str): Email subject
        template_name (str): Path to the email template (HTML)
        context (dict): Context data for the template
        recipient_list (list): List of recipient email addresses
        from_email (str, optional): Sender email. Defaults to DEFAULT_FROM_EMAIL
        fail_silently (bool): If False, raise exceptions on error
    
    Returns:
        int: Number of successfully sent emails
    
    Example:
        send_template_email(
            subject='Booking Confirmation',
            template_name='emails/booking_confirmation.html',
            context={'user': user, 'booking': booking},
            recipient_list=[user.email]
        )
    """
    try:
        html_content = render_to_string(template_name, context)
        return send_html_email(
            subject=subject,
            html_content=html_content,
            recipient_list=recipient_list,
            from_email=from_email,
            fail_silently=fail_silently
        )
    except Exception as e:
        logger.error(f"Error sending template email: {e}")
        if not fail_silently:
            raise
        return 0


def send_booking_confirmation_email(user, booking):
    """
    Send a booking confirmation email to the user.
    
    Args:
        user: User object
        booking: Booking object
    
    Returns:
        int: Number of successfully sent emails
    """
    subject = f'Booking Confirmation - {booking.item.name}'
    message = f"""
Dear {user.username},

Your booking has been confirmed!

Item: {booking.item.name}
Start Date: {booking.start_date}
End Date: {booking.end_date}
Total Price: ${booking.total_price}

Thank you for using Rental Marketplace!

Best regards,
Rental Marketplace Team
    """
    
    return send_simple_email(
        subject=subject,
        message=message.strip(),
        recipient_list=[user.email],
        fail_silently=True
    )


def send_welcome_email(user):
    """
    Send a welcome email to a newly registered user.
    
    Args:
        user: User object
    
    Returns:
        int: Number of successfully sent emails
    """
    subject = 'Welcome to Rental Marketplace!'
    message = f"""
Dear {user.username},

Welcome to Rental Marketplace! We're excited to have you on board.

You can now:
- Browse and rent items from other users
- List your own items for rent
- Manage your bookings and earnings

If you have any questions, feel free to reach out to our support team.

Best regards,
Rental Marketplace Team
    """
    
    return send_simple_email(
        subject=subject,
        message=message.strip(),
        recipient_list=[user.email],
        fail_silently=True
    )


def send_notification_email(user, notification_type, context):
    """
    Send a notification email based on the notification type.
    
    Args:
        user: User object
        notification_type (str): Type of notification (booking, payment, message, etc.)
        context (dict): Additional context data for the email
    
    Returns:
        int: Number of successfully sent emails
    """
    notification_subjects = {
        'booking_request': 'New Booking Request',
        'booking_approved': 'Your Booking Has Been Approved',
        'booking_rejected': 'Booking Request Update',
        'payment_received': 'Payment Received',
        'new_message': 'You Have a New Message',
        'review_reminder': 'Please Review Your Recent Rental',
    }
    
    subject = notification_subjects.get(notification_type, 'Notification from Rental Marketplace')
    
    message = f"""
Dear {user.username},

{context.get('message', 'You have a new notification.')}

Best regards,
Rental Marketplace Team
    """
    
    return send_simple_email(
        subject=subject,
        message=message.strip(),
        recipient_list=[user.email],
        fail_silently=True)


def send_password_reset_otp(user, otp_code):
    """
    Send password reset OTP via email.
    
    Args:
        user: User object
        otp_code: The OTP code to send
    
    Returns:
        bool: True if the email was accepted for delivery, else False
    """
    subject = 'Password Reset OTP - Rental Marketplace'
    message = f"""
Dear {user.username},

You have requested to reset your password for your Rental Marketplace account.

Your One-Time Password (OTP) is: {otp_code}

This OTP will expire in 10 minutes.

If you did not request a password reset, please ignore this email and your password will remain unchanged.

Best regards,
Rental Marketplace Team
    """
    
    try:
        return send_simple_email(
            subject=subject,
            message=message.strip(),
            recipient_list=[user.email],
            fail_silently=False,
        ) > 0
    except Exception:
        logger.exception('Could not send password reset OTP to user id=%s', user.pk)
        return False