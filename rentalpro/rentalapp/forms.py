from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

from .models import RentalListing, RentalListingPhoto, RentalReview, UserProfile


LISTING_CATEGORIES = [
    ('Power tools', 'Power tools'),
    ('Garden & outdoor', 'Garden & outdoor'),
    ('Ladders & access', 'Ladders & access'),
    ('Cleaning', 'Cleaning'),
    ('Other', 'Other'),
]


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned_images = []
        for image in data:
            cleaned_images.append(super().clean(image, initial))
        return cleaned_images


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')
    email = forms.EmailField()
    phone_number = forms.CharField(
        max_length=20,
        label='Phone number',
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9().\-\s]{7,20}$',
                message='Enter a valid phone number.',
            ),
        ],
        widget=forms.TelInput(attrs={
            'class': 'form-control',
            'autocomplete': 'tel',
            'placeholder': '+91 98765 43210',
        }),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email


class RentalListingForm(forms.ModelForm):
    images = MultipleImageField(
        required=False,
        label='Tool photos',
        widget=MultipleImageInput(attrs={
            'accept': 'image/*',
            'class': 'listing-photo-input',
        }),
    )
    category = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={
            'list': 'listing-category-suggestions',
            'placeholder': 'e.g. Power tools or enter your own',
            'autocomplete': 'off',
        }),
    )

    class Meta:
        model = RentalListing
        fields = [
            'title',
            'category',
            'brand',
            'description',
            'city',
            'daily_price',
            'security_deposit',
            'image',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Cordless impact drill'}),
            'brand': forms.TextInput(attrs={'placeholder': 'e.g. Bosch'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the tool and what renters should know.'}),
            'city': forms.TextInput(attrs={'placeholder': 'Your city'}),
            'daily_price': forms.NumberInput(attrs={'min': '1', 'step': '0.01', 'placeholder': '350'}),
            'security_deposit': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '1500'}),
            'image': forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'capture': 'environment',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()

    def clean_security_deposit(self):
        amount = self.cleaned_data['security_deposit']
        if amount < 0:
            raise forms.ValidationError('The security deposit cannot be negative.')
        return amount

    def save_uploaded_photos(self, listing):
        for image in self.cleaned_data.get('images', []):
            RentalListingPhoto.objects.create(listing=listing, image=image)


class UserAccountForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar_image', 'phone_number']
        widgets = {
            'avatar_image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'phone_number': forms.TelInput(attrs={'placeholder': '+91 98765 43210'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class ThemeSettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['theme']
        widgets = {
            'theme': forms.RadioSelect,
        }


class RentalRequestForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'The end date must be on or after the start date.')
        return cleaned_data


class RentalReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(rating, f'{rating} star{"s" if rating != 1 else ""}') for rating in range(1, 6)],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = RentalReview
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'maxlength': 1000,
                'placeholder': 'Share your experience with this item.',
            }),
        }
