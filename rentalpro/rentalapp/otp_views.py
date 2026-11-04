"""
Views for OTP-based password reset functionality.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import login
from rentalapp.models import PasswordResetOTP
from rentalapp.utils import send_password_reset_otp

OTP_EXPIRY_MINUTES = 10


def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """Handle forgot password - request OTP."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'accounts/forgot_password.html')
        
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            
            # Create OTP
            ip_address = get_client_ip(request)
            otp_obj = PasswordResetOTP.create_otp(user, expiry_minutes=OTP_EXPIRY_MINUTES, ip_address=ip_address)
            
            # Send OTP via email
            if not send_password_reset_otp(user, otp_obj.otp):
                otp_obj.delete()
                messages.error(request, 'We could not send the email right now. Please try again in a minute.')
                return render(request, 'accounts/forgot_password.html')
            
            # Store user email in session for verification step
            request.session['reset_email'] = email
            request.session['otp_id'] = otp_obj.id
            
            messages.success(request, 'An OTP has been sent to your email address.')
            return redirect('ui_preview:verify_otp')
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            messages.success(request, 'If an account exists with this email, an OTP has been sent.')
            return render(request, 'accounts/forgot_password.html')
    
    return render(request, 'accounts/forgot_password.html')




@require_http_methods(["GET", "POST"])
def verify_otp(request):
    """Verify OTP and show time remaining."""
    reset_email = request.session.get('reset_email')
    otp_id = request.session.get('otp_id')
    
    if not reset_email or not otp_id:
        messages.error(request, 'Please request a password reset first.')
        return redirect('ui_preview:forgot_password')
    
    try:
        otp_obj = PasswordResetOTP.objects.get(id=otp_id)
    except PasswordResetOTP.DoesNotExist:
        messages.error(request, 'Invalid OTP session. Please try again.')
        return redirect('ui_preview:forgot_password')
    
    # Check if OTP is still valid
    if not otp_obj.is_valid():
        messages.error(request, 'OTP has expired. Please request a new one.')
        del request.session['reset_email']
        del request.session['otp_id']
        return redirect('ui_preview:forgot_password')
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        
        if not entered_otp:
            messages.error(request, 'Please enter the OTP.')
            return render(request, 'accounts/verify_otp.html', {
                'email': reset_email,
                'time_remaining': otp_obj.time_remaining()
            })
        
        if entered_otp == otp_obj.otp and otp_obj.is_valid():
            # OTP is correct
            otp_obj.mark_as_used()
            request.session['otp_verified'] = True
            messages.success(request, 'OTP verified successfully. Please set your new password.')
            return redirect('ui_preview:reset_password')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'accounts/verify_otp.html', {
                'email': reset_email,
                'time_remaining': otp_obj.time_remaining()
            })
    
    return render(request, 'accounts/verify_otp.html', {
        'email': reset_email,
        'time_remaining': otp_obj.time_remaining()
    })


@require_http_methods(["GET", "POST"])
def reset_password(request):
    """Reset password after OTP verification."""
    reset_email = request.session.get('reset_email')
    otp_verified = request.session.get('otp_verified')
    
    if not reset_email or not otp_verified:
        messages.error(request, 'Please complete OTP verification first.')
        return redirect('ui_preview:forgot_password')
    
    User = get_user_model()
    try:
        user = User.objects.get(email__iexact=reset_email, is_active=True)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('ui_preview:forgot_password')
    
    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Clear session
            del request.session['reset_email']
            del request.session['otp_verified']
            if 'otp_id' in request.session:
                del request.session['otp_id']
            
            # Log the user in
            login(request, user)
            
            messages.success(request, 'Your password has been reset successfully! Please log in with your new password.')
            return redirect('ui_preview:login')
    else:
        form = SetPasswordForm(user)
    
    return render(request, 'accounts/reset_password.html', {'form': form})


@require_http_methods(["POST"])
def resend_otp(request):
    """Resend OTP to the user's email."""
    reset_email = request.session.get('reset_email')
    
    if not reset_email:
        messages.error(request, 'Please request a password reset first.')
        return redirect('ui_preview:forgot_password')
    
    User = get_user_model()
    try:
        user = User.objects.get(email__iexact=reset_email, is_active=True)
        
        # Create new OTP
        ip_address = get_client_ip(request)
        otp_obj = PasswordResetOTP.create_otp(user, expiry_minutes=OTP_EXPIRY_MINUTES, ip_address=ip_address)
        
        # Send OTP via email
        if not send_password_reset_otp(user, otp_obj.otp):
            otp_obj.delete()
            messages.error(request, 'We could not send the email right now. Please try again in a minute.')
            return redirect('ui_preview:verify_otp')
        
        # Update session with new OTP ID
        request.session['otp_id'] = otp_obj.id
        
        messages.success(request, 'A new OTP has been sent to your email address.')
        
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('ui_preview:verify_otp')