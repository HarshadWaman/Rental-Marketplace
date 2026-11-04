# Email Configuration - Usage Guide

## Quick Setup

1. **Get Gmail App Password:**
   - Enable 2-Factor Authentication on your Google Account
   - Visit: https://myaccount.google.com/apppasswords
   - Generate a new App Password for "Mail"
   - Copy the 16-character password

2. **Set Environment Variables (Recommended):**
   ```bash
   # Windows PowerShell
   $env:EMAIL_HOST_USER="your-email@gmail.com"
   $env:EMAIL_HOST_PASSWORD="your-16-char-app-password"
   ```

3. **Or Edit settings.py directly (Not recommended for production):**
   Replace the default values in `rentalpro/settings.py`:
   ```python
   EMAIL_HOST_USER = 'your-actual-email@gmail.com'
   EMAIL_HOST_PASSWORD = 'your-actual-app-password'
   ```

## Test Email Configuration

```bash
python manage.py test_email recipient@example.com
```

## Usage Examples

### 1. Simple Text Email
```python
from rentalapp.utils import send_simple_email

send_simple_email(
    subject='Welcome!',
    message='Thank you for signing up.',
    recipient_list=['user@example.com']
)
```

### 2. HTML Email
```python
from rentalapp.utils import send_html_email

html = '<h1>Welcome!</h1><p>Thank you for signing up.</p>'
send_html_email(
    subject='Welcome!',
    html_content=html,
    recipient_list=['user@example.com']
)
```

### 3. Template-based Email
```python
from rentalapp.utils import send_template_email

send_template_email(
    subject='Booking Confirmation',
    template_name='emails/booking.html',
    context={'user': user, 'booking': booking},
    recipient_list=[user.email]
)
```

### 4. Pre-built Email Functions
```python
from rentalapp.utils import (
    send_welcome_email,
    send_booking_confirmation_email,
    send_notification_email
)

# Welcome email
send_welcome_email(user)

# Booking confirmation
send_booking_confirmation_email(user, booking)

# Custom notification
send_notification_email(
    user=user,
    notification_type='booking_request',
    context={'message': 'You have a new booking request!'}
)
```

## Using Other Email Providers

### Outlook/Hotmail
```python
EMAIL_HOST = 'smtp-mail.outlook.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

### Yahoo
```python
EMAIL_HOST = 'smtp.mail.yahoo.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

### Custom SMTP
```python
EMAIL_HOST = 'smtp.yourprovider.com'
EMAIL_PORT = 587  # or 465 for SSL
EMAIL_USE_TLS = True  # or False
EMAIL_USE_SSL = False  # or True for port 465
```

## Development Mode

If credentials are not configured, emails will be printed to console instead of sent.

## Security Best Practices

- Never commit credentials to version control
- Always use environment variables in production
- Use App Passwords, not regular passwords
- Rotate passwords regularly
- Keep EMAIL_HOST_PASSWORD in .env file (add .env to .gitignore)
