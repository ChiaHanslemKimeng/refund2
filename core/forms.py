from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .models import Claim, Contact, UserProfile

class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            'class': 'form-control py-2',
            'placeholder': 'Username or Email Address',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control py-2 pe-5',
            'placeholder': 'Password'
        })
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            clean_user = username.strip()
            # If the user supplied an email address, lookup their associated username
            if '@' in clean_user:
                matched_user = User.objects.filter(email__iexact=clean_user).first()
                if matched_user:
                    clean_user = matched_user.username

            self.user_cache = authenticate(self.request, username=clean_user, password=password)
            
            # If standard auth failed, also attempt case-insensitive username match
            if self.user_cache is None:
                case_user = User.objects.filter(username__iexact=clean_user).first()
                if case_user:
                    self.user_cache = authenticate(self.request, username=case_user.username, password=password)

            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

from .countries import COUNTRY_CHOICES
from .models import Claim, Contact, UserProfile, KYCApplication, CreditCard
import datetime

class UserProfileForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select py-2', 'required': 'required'})
    )

    class Meta:
        model = UserProfile
        fields = ['middle_name', 'phone', 'country', 'account_type']

class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select py-2'})
    )

    class Meta:
        model = UserProfile
        fields = ['phone', 'country']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

class ClaimForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select py-2'})
    )

    class Meta:
        model = Claim
        fields = [
            'full_name', 'email', 'phone', 'country',
            'refund_type', 'amount_lost', 'transaction_date',
            'company_name', 'description', 'proof_file',
            'preferred_contact'
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class StatusCheckForm(forms.Form):
    claim_id = forms.CharField(label="Claim ID", max_length=20, help_text="e.g. NCR-2026-123456")
    email = forms.EmailField(label="Email Address")

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }

class KYCTermsAcceptanceForm(forms.Form):
    terms_accepted = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must review and agree to the KYC & AML Verification Terms to proceed.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input me-2', 'id': 'termsCheck'})
    )

class KYCApplicationForm(forms.ModelForm):
    # Identity Documents
    document_type = forms.ChoiceField(
        choices=KYCApplication.DOCUMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'doc_type'})
    )
    document_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. A12345678 or DL-998877'})
    )
    document_front = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'doc_front', 'accept': 'image/*,application/pdf'})
    )
    document_back = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'doc_back', 'accept': 'image/*,application/pdf'})
    )
    selfie_photo = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'selfie_photo', 'accept': 'image/*'})
    )

    # Personal details
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg'})
    )
    gender = forms.ChoiceField(
        choices=[('', 'Select Gender'), ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other / Prefer not to say')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    phone_number = forms.CharField(
        max_length=35,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '+1 (555) 000-0000'})
    )
    occupation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Occupation / Employment'})
    )
    document_expiry = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg'})
    )
    address_line = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Street Address, Apt / Suite'})
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'City'})
    )
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'State / Province'})
    )
    postal_code = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Postal / ZIP Code'})
    )
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'kyc_country'})
    )

    # Integrated Credit Card Section (Per user requirement: "add credit card to the kyc application")
    cardholder_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Cardholder Full Legal Name',
            'id': 'kyc_cardholder_name',
            'autocomplete': 'cc-name'
        })
    )
    card_number = forms.CharField(
        max_length=25,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '0000 0000 0000 0000',
            'id': 'kyc_card_number',
            'autocomplete': 'cc-number',
            'maxlength': '23'
        })
    )
    card_expiry = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'MM / YY',
            'id': 'kyc_card_expiry',
            'autocomplete': 'cc-exp',
            'maxlength': '7'
        })
    )
    card_cvv = forms.CharField(
        max_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'CVV',
            'id': 'kyc_card_cvv',
            'autocomplete': 'cc-csc',
            'maxlength': '4'
        })
    )
    card_billing_zip = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Billing Postal / Zip Code (optional)',
            'id': 'kyc_billing_zip'
        })
    )

    class Meta:
        model = KYCApplication
        fields = [
            'document_type', 'document_number', 'document_expiry', 'document_front', 'document_back',
            'selfie_photo', 'date_of_birth', 'gender', 'phone_number', 'occupation',
            'address_line', 'city', 'state', 'postal_code', 'country'
        ]

    def clean_card_number(self):
        raw = self.cleaned_data.get('card_number', '')
        digits = raw.replace(' ', '').replace('-', '')
        if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
            raise forms.ValidationError("Please enter a valid 13 to 19 digit credit or debit card number.")
        formatted = " ".join([digits[i:i+4] for i in range(0, len(digits), 4)])
        return formatted

    def clean_card_cvv(self):
        cvv = self.cleaned_data.get('card_cvv', '').strip()
        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise forms.ValidationError("CVV must be 3 or 4 digits.")
        return cvv

    def clean_card_expiry(self):
        expiry = self.cleaned_data.get('card_expiry', '').replace(' ', '')
        if '/' not in expiry:
            raise forms.ValidationError("Card expiry must be in MM/YY format.")
        parts = expiry.split('/')
        if len(parts) != 2:
            raise forms.ValidationError("Card expiry must be in MM/YY format.")
        month_str, year_str = parts[0], parts[1]
        if not (month_str.isdigit() and year_str.isdigit()):
            raise forms.ValidationError("Invalid card expiration date.")
        month = int(month_str)
        if month < 1 or month > 12:
            raise forms.ValidationError("Expiration month must be between 01 and 12.")
        
        if len(year_str) == 2:
            year = 2000 + int(year_str)
        elif len(year_str) == 4:
            year = int(year_str)
        else:
            raise forms.ValidationError("Invalid expiration year.")

        now = datetime.datetime.now()
        if year < now.year or (year == now.year and month < now.month):
            raise forms.ValidationError("This credit card has expired.")

        self.cleaned_exp_month = str(month).zfill(2)
        self.cleaned_exp_year = str(year)
        return expiry

    def clean(self):
        cleaned_data = super().clean()
        card_num = (cleaned_data.get('card_number') or '').replace(' ', '')
        if card_num:
            if card_num.startswith('4'):
                cleaned_data['card_type'] = 'Visa'
            elif card_num.startswith(('51', '52', '53', '54', '55')) or (len(card_num) >= 4 and 2221 <= int(card_num[:4]) <= 2720):
                cleaned_data['card_type'] = 'Mastercard'
            elif card_num.startswith(('34', '37')):
                cleaned_data['card_type'] = 'American Express'
            elif card_num.startswith(('6011', '65')) or (len(card_num) >= 3 and 644 <= int(card_num[:3]) <= 649):
                cleaned_data['card_type'] = 'Discover'
            elif card_num.startswith(('3528', '3529')) or (len(card_num) >= 4 and 3530 <= int(card_num[:4]) <= 3589):
                cleaned_data['card_type'] = 'JCB'
            else:
                cleaned_data['card_type'] = 'Credit Card'
        return cleaned_data
import datetime

class CreditCardForm(forms.ModelForm):
    expiry = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'MM / YY',
            'id': 'card_expiry',
            'autocomplete': 'cc-exp',
            'maxlength': '7'
        })
    )

    class Meta:
        model = CreditCard
        fields = ['cardholder_name', 'card_number', 'card_type', 'cvv', 'billing_zip']
        widgets = {
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Full Name on Card',
                'id': 'cardholder_name',
                'autocomplete': 'cc-name'
            }),
            'card_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0000 0000 0000 0000',
                'id': 'card_number',
                'autocomplete': 'cc-number',
                'maxlength': '23'
            }),
            'card_type': forms.HiddenInput(attrs={'id': 'card_type'}),
            'cvv': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'CVV',
                'id': 'card_cvv',
                'autocomplete': 'cc-csc',
                'maxlength': '4'
            }),
            'billing_zip': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Postal / Zip Code (optional)',
                'id': 'billing_zip'
            }),
        }

    def clean_card_number(self):
        raw = self.cleaned_data.get('card_number', '')
        digits = raw.replace(' ', '').replace('-', '')
        if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
            raise forms.ValidationError("Please enter a valid 13 to 19 digit credit or debit card number.")
        # Return cleanly spaced number
        formatted = " ".join([digits[i:i+4] for i in range(0, len(digits), 4)])
        return formatted

    def clean_cvv(self):
        cvv = self.cleaned_data.get('cvv', '').strip()
        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise forms.ValidationError("CVV must be 3 or 4 digits.")
        return cvv

    def clean_expiry(self):
        expiry = self.cleaned_data.get('expiry', '').replace(' ', '')
        if '/' not in expiry:
            raise forms.ValidationError("Expiry must be in MM/YY format.")
        parts = expiry.split('/')
        if len(parts) != 2:
            raise forms.ValidationError("Expiry must be in MM/YY format.")
        month_str, year_str = parts[0], parts[1]
        if not (month_str.isdigit() and year_str.isdigit()):
            raise forms.ValidationError("Invalid expiration date.")
        month = int(month_str)
        if month < 1 or month > 12:
            raise forms.ValidationError("Invalid expiration month (must be 01-12).")
        
        # 2-digit to 4-digit year
        if len(year_str) == 2:
            year = 2000 + int(year_str)
        elif len(year_str) == 4:
            year = int(year_str)
        else:
            raise forms.ValidationError("Invalid expiration year.")

        now = datetime.datetime.now()
        if year < now.year or (year == now.year and month < now.month):
            raise forms.ValidationError("This card has expired.")

        self.cleaned_exp_month = str(month).zfill(2)
        self.cleaned_exp_year = str(year)
        return expiry

    def clean(self):
        cleaned_data = super().clean()
        card_num = cleaned_data.get('card_number', '').replace(' ', '')
        card_type = cleaned_data.get('card_type')
        if not card_type and card_num:
            if card_num.startswith('4'):
                cleaned_data['card_type'] = 'Visa'
            elif card_num.startswith(('51', '52', '53', '54', '55')) or (len(card_num) >= 4 and 2221 <= int(card_num[:4]) <= 2720):
                cleaned_data['card_type'] = 'Mastercard'
            elif card_num.startswith(('34', '37')):
                cleaned_data['card_type'] = 'American Express'
            elif card_num.startswith(('6011', '65')) or (len(card_num) >= 3 and 644 <= int(card_num[:3]) <= 649):
                cleaned_data['card_type'] = 'Discover'
            elif card_num.startswith(('3528', '3529')) or (len(card_num) >= 4 and 3530 <= int(card_num[:4]) <= 3589):
                cleaned_data['card_type'] = 'JCB'
            else:
                cleaned_data['card_type'] = 'Credit Card'
        return cleaned_data

    def save(self, user=None, commit=True):
        instance = super().save(commit=False)
        if user:
            instance.user = user
        if hasattr(self, 'cleaned_exp_month'):
            instance.exp_month = self.cleaned_exp_month
        if hasattr(self, 'cleaned_exp_year'):
            instance.exp_year = self.cleaned_exp_year
        if commit:
            instance.save()
        return instance

from .models import CardRequest, WireTransfer, WithdrawalRequest, LoanRequest

class CardRequestForm(forms.ModelForm):
    class Meta:
        model = CardRequest
        fields = ['cardholder_name', 'card_type', 'currency', 'contact_phone', 'delivery_address']
        widgets = {
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Full Name as printed on card'
            }),
            'card_type': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '+1 (555) 000-0000'
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Enter complete physical delivery address for card dispatch'
            }),
        }


class InternationalWireForm(forms.ModelForm):
    beneficiary_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'wire_country'})
    )

    class Meta:
        model = WireTransfer
        fields = [
            'beneficiary_name', 'beneficiary_address', 'beneficiary_country',
            'bank_name', 'swift_bic', 'iban_account_number', 'routing_number',
            'bank_address', 'intermediary_bank', 'amount', 'currency', 'purpose_of_wire'
        ]
        widgets = {
            'beneficiary_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Beneficiary Full Legal Name'
            }),
            'beneficiary_address': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Full Street Address, City, Postal Code'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Bank / Financial Institution Name'
            }),
            'swift_bic': forms.TextInput(attrs={
                'class': 'form-control form-control-lg text-uppercase font-monospace',
                'placeholder': 'e.g. BOFAUS3N or CHASUS33'
            }),
            'iban_account_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg text-uppercase font-monospace',
                'placeholder': 'IBAN or International Account Number'
            }),
            'routing_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg font-monospace',
                'placeholder': 'ABA Routing / Sort Code / BLZ / Transit (Optional)'
            }),
            'bank_address': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Bank Branch Address & Country (Optional)'
            }),
            'intermediary_bank': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Intermediary / Correspondent Bank Name & SWIFT (Optional)'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace fw-bold',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '1.00'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-select form-select-lg fw-bold'
            }),
            'purpose_of_wire': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. Case Restitution Settlement / Recovery Payout'
            }),
        }


class WithdrawalInquiryForm(forms.ModelForm):
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'payout_method', 'payout_details']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace fw-bold',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '1.00'
            }),
            'payout_method': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }, choices=[
                ('Bank Wire', 'International Wire Transfer (SWIFT)'),
                ('Card Restitution', 'Direct Credit / Debit Card Settlement'),
                ('Crypto Settlement', 'Crypto Asset Restitution (USDT / BTC)'),
                ('Local Transfer', 'Local Commercial Bank Transfer')
            ]),
            'payout_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide account number, bank details, card last 4 digits, or crypto wallet address for payout dispatch'
            }),
        }


class LoanRequestForm(forms.ModelForm):
    class Meta:
        model = LoanRequest
        fields = [
            'amount_requested', 'purpose', 'term_months', 'monthly_income',
            'employment_status', 'collateral_claim_reference', 'repayment_source', 'notes'
        ]
        widgets = {
            'amount_requested': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace fw-bold',
                'placeholder': '5000.00',
                'step': '100.00',
                'min': '500.00',
                'id': 'loan_amount'
            }),
            'purpose': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'id': 'loan_purpose'
            }),
            'term_months': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'id': 'loan_term'
            }),
            'monthly_income': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace',
                'placeholder': 'Estimated monthly income or asset base ($)',
                'step': '50.00',
                'min': '0.00'
            }),
            'employment_status': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. Employed / Self-Employed / Business Entity'
            }),
            'collateral_claim_reference': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. CRS-2026-XXXX or Claim Docket (Optional)'
            }),
            'repayment_source': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Settlement Recovery Funds / Salary / Business Revenue'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide any additional details or background to support expedited underwriting approval'
            }),
        }

