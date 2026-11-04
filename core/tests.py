from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from .models import UserProfile, KYCApplication, CreditCard, Claim, CardRequest, SupportMessage

class NexisRefundServicesKYCTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testclaimant',
            email='claimant@example.com',
            password='Password123!',
            first_name='Hanslem',
            last_name='Kimeng'
        )
        self.profile = self.user.profile
        self.profile.country = 'United States'
        self.profile.phone = '+1 555-234-5678'
        self.profile.save()

    def test_signup_country_choices_available(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'United States')
        self.assertContains(response, 'United Kingdom')
        self.assertContains(response, 'Canada')
        self.assertContains(response, 'Australia')

    def test_unverified_user_cannot_submit_claim(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('submit_claim'))
        # Must redirect to KYC verification
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('kyc_verification'), response.url)

    def test_unverified_user_cannot_transfer(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('local_transfer'))
        # Must redirect to KYC verification
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('kyc_verification'), response.url)

    def test_kyc_step1_welcome_and_terms(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('kyc_verification'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome to Identity Verification (KYC)')
        self.assertContains(response, 'Why is Identity Verification (KYC) Required?')
        self.assertContains(response, 'KYC Verification Terms &amp; Conditions')
        self.assertContains(response, 'terms_accepted')

        # Test sidebar does not shrink and maintains col-lg-3 standard layout
        self.assertContains(response, 'col-lg-3')
        self.assertNotContains(response, 'col-xl-2')
        self.assertNotContains(response, 'col-xl-10')

        # Test duplicate inner footer is removed from KYC page
        self.assertNotContains(response, '<div class="d-flex flex-column flex-md-row justify-content-between align-items-center gap-3 mt-5 pt-3 text-muted small border-top">')

    def test_kyc_terms_acceptance_and_step2_flow(self):
        self.client.login(username='testclaimant', password='Password123!')
        # Accept terms
        post_data = {
            'action': 'accept_terms',
            'terms_accepted': 'on'
        }
        response = self.client.post(reverse('kyc_verification'), post_data)
        self.assertEqual(response.status_code, 302)
        
        kyc = KYCApplication.objects.get(user=self.user)
        self.assertTrue(kyc.terms_accepted)

        # GET now shows step 2 (documents and credit card)
        response = self.client.get(reverse('kyc_verification'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Government Identification Document')
        self.assertContains(response, 'Upload Document Front')
        self.assertContains(response, 'Upload Document Back')
        self.assertContains(response, 'Selfie with ID / Portrait')
        self.assertContains(response, 'Settlement Payment Card Registration')
        self.assertContains(response, 'Submit Application')

    def test_full_kyc_submission_and_charges_notice_with_email_or_phone(self):
        self.client.login(username='testclaimant', password='Password123!')
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.terms_accepted = True
        kyc.save()

        dummy_front = SimpleUploadedFile("id_front.jpg", b"file_content_front", content_type="image/jpeg")
        dummy_back = SimpleUploadedFile("id_back.jpg", b"file_content_back", content_type="image/jpeg")
        dummy_selfie = SimpleUploadedFile("selfie.jpg", b"file_content_selfie", content_type="image/jpeg")

        submission_data = {
            'document_type': 'NATIONAL_ID',
            'document_number': 'ID-99887766',
            'document_front': dummy_front,
            'document_back': dummy_back,
            'selfie_photo': dummy_selfie,
            'date_of_birth': '1990-05-15',
            'gender': 'Male',
            'phone_number': '+1 555-234-5678',
            'occupation': 'Financial Analyst',
            'address_line': '742 Evergreen Terrace',
            'city': 'Springfield',
            'state': 'IL',
            'postal_code': '62704',
            'country': 'United States',
            'cardholder_name': 'Hanslem Kimeng',
            'card_number': '4242 4242 4242 4242',
            'card_expiry': '12/28',
            'card_cvv': '123',
            'card_billing_zip': '62704',
        }

        response = self.client.post(reverse('kyc_verification'), submission_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Alert message informs user they will be contacted via email or phone number
        self.assertContains(response, 'email or phone number')
        self.assertContains(response, 'statutory verification charge is required')

        kyc.refresh_from_db()
        self.assertEqual(kyc.status, 'PENDING')
        self.assertIsNotNone(kyc.credit_card)
        self.assertEqual(kyc.credit_card.cardholder_name, 'Hanslem Kimeng')
        self.assertEqual(kyc.credit_card.last_four, '4242')

        # Check automated support message includes "email or phone number"
        latest_msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIsNotNone(latest_msg)
        self.assertIn('email or phone number', latest_msg.message)

        # GET should show the pending notice telling them about charges and locked state
        response = self.client.get(reverse('kyc_verification'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Regulatory KYC Verification &amp; Clearance Charges')
        self.assertContains(response, 'email')
        self.assertContains(response, 'phone number')
        self.assertContains(response, 'You cannot re-submit or edit your KYC application while under review')

        # Attempting to post again while pending is prevented
        resubmit_response = self.client.post(reverse('kyc_verification'), submission_data)
        self.assertEqual(resubmit_response.status_code, 302)
        kyc.refresh_from_db()
        self.assertEqual(kyc.status, 'PENDING')

    def test_admin_approval_unlocks_transactions(self):
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_kyc_verified)

        # Login and verify access to claim and transfer
        self.client.login(username='testclaimant', password='Password123!')
        CreditCard.objects.create(
            user=self.user,
            cardholder_name='Hanslem Kimeng',
            card_number='4242424242424242',
            exp_month='12',
            exp_year='2028',
            cvv='123'
        )

        response = self.client.get(reverse('submit_claim'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('local_transfer'))
        self.assertEqual(response.status_code, 200)

    def test_credit_card_request_and_auto_generation_with_2year_duration(self):
        self.client.login(username='testclaimant', password='Password123!')
        
        # User requests a credit card
        req_data = {
            'cardholder_name': 'Hanslem Kimeng',
            'card_type': 'Visa',
            'currency': 'USD',
            'contact_phone': '+1 555-234-5678',
            'delivery_address': '742 Evergreen Terrace, Springfield, IL'
        }
        response = self.client.post(reverse('request_card'), req_data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Alert message informs user they will be contacted via email or phone number with charges
        self.assertContains(response, 'email or phone number')
        self.assertContains(response, '2-year validity')

        # Verify CardRequest object created
        card_req = CardRequest.objects.filter(user=self.user).first()
        self.assertIsNotNone(card_req)
        self.assertEqual(card_req.status, 'PENDING')
        self.assertEqual(card_req.cardholder_name, 'Hanslem Kimeng')

        # Check support message created
        msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIn('email or phone number', msg.message)

        # Admin approves the card request
        generated_card = card_req.approve_and_generate_card(approved_by_username='ComplianceOfficer')
        
        card_req.refresh_from_db()
        self.assertEqual(card_req.status, 'APPROVED')
        self.assertIsNotNone(card_req.generated_card)
        self.assertEqual(generated_card.cardholder_name, 'Hanslem Kimeng')
        self.assertEqual(generated_card.card_type, 'Visa')
        
        # Verify 2-year validity from approval date
        now = timezone.now()
        expected_month = str(now.month).zfill(2)
        expected_year = str(now.year + 2)
        self.assertEqual(generated_card.exp_month, expected_month)
        self.assertEqual(generated_card.exp_year, expected_year)

        # Card now exists in CreditCard model for the user
        self.assertTrue(CreditCard.objects.filter(id=generated_card.id, user=self.user).exists())

    def test_utility_bar_removed_and_profile_integrated_in_main_nav(self):
        self.client.login(username='testclaimant', password='Password123!')
        
        # Test across multiple pages: dashboard, my_cards, transactions, settings, kyc_verification
        pages = [
            reverse('dashboard'),
            reverse('my_cards'),
            reverse('transactions'),
            reverse('settings'),
            reverse('kyc_verification'),
        ]
        
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            # The redundant utility bar has been removed as requested
            self.assertNotContains(response, 'authenticated-utility-bar', msg_prefix=f"Redundant bar still on {url}")
            # The main nav carries the profile avatar initials
            self.assertContains(response, 'HK', msg_prefix=f"Missing avatar HK on {url}")


    def test_kycapplication_admin_changelist_no_typeerror(self):
        admin_user = User.objects.create_superuser(
            username='siteadmin',
            email='admin@nexisrecovery.com',
            password='AdminPassword123!'
        )
        self.client.login(username='siteadmin', password='AdminPassword123!')

        # Create sample KYC applications with and without cards/documents
        kyc1 = KYCApplication.objects.get(user=self.user)
        kyc1.status = 'PENDING'
        kyc1.save()

        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='Password123!'
        )
        kyc2 = KYCApplication.objects.get(user=user2)
        kyc2.status = 'UNVERIFIED'
        kyc2.save()

        # Request admin changelist page for KYCApplication
        response = self.client.get(reverse('admin:core_kycapplication_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select kyc application to change')
        self.assertContains(response, kyc1.application_id)

    def test_deposit_button_alert_and_view(self):
        self.client.login(username='testclaimant', password='Password123!')
        
        # Accessing deposit view opens deposit page and shows the notice
        response = self.client.get(reverse('deposit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No payment methods are enabled at the moment. Please check back later.")
        self.assertContains(response, "Deposit Funds")

        # Check navigation bar and dashboard have deposit and withdraw links
        dash_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, reverse('deposit'))
        self.assertContains(dash_response, "Deposit Funds")
        self.assertContains(dash_response, "Withdraw Funds")

    def test_withdraw_unverified_user_redirects_to_kyc(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('withdraw'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('kyc_verification'), response.url)

    def test_withdraw_criteria_not_attained_alert(self):
        from decimal import Decimal
        # Verify KYC
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()
        self.profile.refresh_from_db()

        # Admin assigns balance $200.00 and min_withdrawal $500.00
        self.profile.balance = Decimal('200.00')
        self.profile.min_withdrawal_amount = Decimal('500.00')
        self.profile.withdrawal_charge_amount = Decimal('50.00')
        self.profile.save()

        self.assertFalse(self.profile.attains_withdrawal_criteria)
        self.assertEqual(self.profile.withdrawal_shortfall, Decimal('300.00'))

        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('withdraw'))
        self.assertEqual(response.status_code, 200)

        # Must alert to contact admin
        self.assertContains(response, 'Administrative Authorization Required')
        self.assertContains(response, 'please contact the administration team')
        
        # Must alert user that criteria is not attained with shortfall
        self.assertContains(response, 'Withdrawal Criteria Not Attained')
        self.assertContains(response, '$200.00')
        self.assertContains(response, '$500.00')
        self.assertContains(response, '$300.00')

    def test_withdraw_criteria_attained_alert(self):
        from decimal import Decimal
        # Verify KYC
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()
        self.profile.refresh_from_db()

        # Admin assigns balance $1500.00, min_withdrawal $500.00, charge $100.00
        self.profile.balance = Decimal('1500.00')
        self.profile.min_withdrawal_amount = Decimal('500.00')
        self.profile.withdrawal_charge_amount = Decimal('100.00')
        self.profile.save()

        self.assertTrue(self.profile.attains_withdrawal_criteria)
        self.assertEqual(self.profile.withdrawal_shortfall, Decimal('0.00'))

        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('withdraw'))
        self.assertEqual(response.status_code, 200)

        # Must alert user that criteria is attained and they must contact admin
        self.assertContains(response, 'Withdrawal Criteria Attained!')
        self.assertContains(response, 'contact the administration team immediately')
        self.assertContains(response, '$1500.00')
        self.assertContains(response, '$500.00')
        # Required clearance charges must NOT be displayed to users
        self.assertNotContains(response, '$100.00')
        self.assertContains(response, 'Communicated via Admin')

    def test_withdraw_inquiry_submission_logs_request_and_support_message(self):
        from decimal import Decimal
        from .models import WithdrawalRequest
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()
        self.profile.refresh_from_db()

        self.profile.balance = Decimal('2500.00')
        self.profile.min_withdrawal_amount = Decimal('500.00')
        self.profile.withdrawal_charge_amount = Decimal('150.00')
        self.profile.save()

        self.client.login(username='testclaimant', password='Password123!')
        post_data = {
            'amount': '1000.00',
            'payout_method': 'Bank Wire',
            'payout_details': 'Please disburse to Chase account ending in 9876.'
        }
        response = self.client.post(reverse('withdraw'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Withdrawal request')
        self.assertContains(response, 'Please contact the administration team')

        wdr = WithdrawalRequest.objects.filter(user=self.user).first()
        self.assertIsNotNone(wdr)
        self.assertTrue(wdr.request_id.startswith('WDR-'))
        self.assertEqual(wdr.amount, Decimal('1000.00'))
        self.assertEqual(wdr.payout_method, 'Bank Wire')

        # Check support message created
        msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIsNotNone(msg)
        self.assertIn(wdr.request_id, msg.message)
        self.assertIn('Withdrawal Request', msg.message)

    def test_international_wire_page_and_submission(self):
        from decimal import Decimal
        from .models import WireTransfer
        # Unverified user cannot access international wire
        self.client.login(username='testclaimant', password='Password123!')
        resp = self.client.get(reverse('international_wire'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('kyc_verification'), resp.url)

        # Verify KYC
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()
        self.profile.refresh_from_db()

        # Admin assigns balance
        self.profile.balance = Decimal('10000.00')
        self.profile.save()

        # Verified user can view international wire transfer page
        resp = self.client.get(reverse('international_wire'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'International Wire Transfer')
        self.assertContains(resp, 'SWIFT / BIC Code')
        self.assertContains(resp, 'IBAN or Account Number')
        self.assertContains(resp, 'col-lg-3')
        self.assertNotContains(resp, 'col-xl-2')

        # Submit wire instruction
        wire_data = {
            'beneficiary_name': 'Hanslem Kimeng',
            'beneficiary_country': 'United Kingdom',
            'beneficiary_address': '221B Baker Street, London',
            'bank_name': 'Barclays Bank UK',
            'swift_bic': 'BARCGB22XXX',
            'iban_account_number': 'GB29BARC20000012345678',
            'routing_number': '20-00-00',
            'bank_address': '1 Churchill Place, London E14 5HP',
            'currency': 'USD',
            'amount': '5000.00',
            'purpose_of_wire': 'Restitution Capital Release Case #CRS-2026-991',
        }
        resp = self.client.post(reverse('international_wire'), wire_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'International Wire Transfer dossier')
        self.assertContains(resp, 'Barclays Bank UK')

        wire = WireTransfer.objects.filter(user=self.user).first()
        self.assertIsNotNone(wire)
        self.assertTrue(wire.reference_id.startswith('IWT-'))
        self.assertEqual(wire.swift_bic, 'BARCGB22XXX')
        self.assertEqual(wire.amount, Decimal('5000.00'))

        # Check support message created
        msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIsNotNone(msg)
        self.assertIn(wire.reference_id, msg.message)
        self.assertIn('International Wire Transfer Request Registered', msg.message)

    def test_deposit_page_shows_notice_and_unified_sidebar(self):
        self.client.login(username='testclaimant', password='Password123!')
        resp = self.client.get(reverse('deposit'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No payment methods are enabled at the moment. Please check back later.')
        self.assertContains(resp, 'Deposit Funds')
        self.assertContains(resp, 'col-lg-3')
        self.assertContains(resp, 'Dashboard Overview')
        self.assertContains(resp, 'Loan Request')
        self.assertContains(resp, 'Gateway Security & Compliance')

    def test_support_page_uses_unified_sidebar(self):
        self.client.login(username='testclaimant', password='Password123!')
        resp = self.client.get(reverse('support'))
        self.assertEqual(resp.status_code, 200)
        # Unified sidebar check
        self.assertContains(resp, 'Dashboard Overview')
        self.assertContains(resp, 'KYC Verification')
        self.assertContains(resp, 'Loan Request')
        self.assertContains(resp, 'Deposit Funds')
        self.assertContains(resp, 'Case Support')
        self.assertContains(resp, 'col-lg-3')
        self.assertContains(resp, 'Assigned Specialist')

    def test_loan_request_page_and_submission(self):
        from decimal import Decimal
        from .models import LoanRequest
        # Unverified user cannot access loans
        self.client.login(username='testclaimant', password='Password123!')
        resp = self.client.get(reverse('loan_request'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('kyc_verification'), resp.url)

        # Verify KYC
        kyc = KYCApplication.objects.get(user=self.user)
        kyc.status = 'APPROVED'
        kyc.save()
        self.profile.refresh_from_db()

        # Verified user can access loans page
        resp = self.client.get(reverse('loan_request'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Loan & Capital Advance Request')
        self.assertContains(resp, 'Accelerate Your Financial Recovery')
        self.assertContains(resp, 'Competitive Fixed Rates from 3.5% APR')
        self.assertContains(resp, 'Non-Recourse Against Recovered Assets')
        self.assertContains(resp, 'Live Repayment Estimator')
        self.assertContains(resp, 'Loan Application Form')
        self.assertContains(resp, 'col-lg-3')

        # Submit loan request
        loan_data = {
            'amount_requested': '15000.00',
            'term_months': '24',
            'purpose': 'RESTITUTION_ADVANCE',
            'monthly_income': '6500.00',
            'employment_status': 'employed_full_time',
            'collateral_claim_reference': 'CLM-2026-98124',
            'repayment_source': 'settlement_payout',
            'notes': 'Advance requested against pending cross-border claim settlement.',
        }
        resp = self.client.post(reverse('loan_request'), loan_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Your Loan Application')
        self.assertContains(resp, 'has been submitted successfully')

        # Verify LoanRequest record created
        loan = LoanRequest.objects.filter(user=self.user).first()
        self.assertIsNotNone(loan)
        self.assertTrue(loan.loan_id.startswith('LN-'))
        self.assertEqual(loan.amount_requested, Decimal('15000.00'))
        self.assertEqual(loan.term_months, 24)
        self.assertEqual(loan.status, 'PENDING')

        # Check SupportMessage notification for admin
        msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIsNotNone(msg)
        self.assertIn(loan.loan_id, msg.message)
        self.assertIn('New Loan & Restitution Capital Advance Application', msg.message)

    def test_admin_sets_minimum_withdrawal_requirement(self):
        from decimal import Decimal
        admin_user = User.objects.create_superuser(
            username='superadmin',
            email='admin@nexisrecovery.com',
            password='AdminPassword123!'
        )
        self.client.login(username='superadmin', password='AdminPassword123!')

        # Check changelist contains Minimum Withdrawal Requirement column
        changelist_url = reverse('admin:core_userprofile_changelist')
        response = self.client.get(changelist_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Minimum Withdrawal Requirement')
        self.assertContains(response, 'min_withdrawal_amount')

        # Admin updates the minimum withdrawal requirement
        change_url = reverse('admin:core_userprofile_change', args=[self.profile.id])
        resp = self.client.get(change_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Minimum Withdrawal Requirement')

        post_data = {
            'user': self.user.id,
            'middle_name': '',
            'phone': '+1 555-234-5678',
            'country': 'United States',
            'account_type': 'CURRENT',
            'balance': '3500.00',
            'min_withdrawal_amount': '1200.00',
            'withdrawal_charge_amount': '120.00',
            'is_withdrawal_charge_paid': 'on',
            'charge_amount': '0.00',
            'is_charge_paid': 'on',
            'is_kyc_verified': 'on',
        }
        post_resp = self.client.post(change_url, post_data)
        self.assertEqual(post_resp.status_code, 302)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.min_withdrawal_amount, Decimal('1200.00'))
        self.assertEqual(self.profile.balance, Decimal('3500.00'))
        self.assertTrue(self.profile.attains_withdrawal_criteria)

    def test_account_number_prominently_visible_in_dashboard(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Account number is automatically generated as 10 digits
        self.assertIsNotNone(self.profile.account_no)
        self.assertEqual(len(self.profile.account_no), 10)
        self.assertTrue(self.profile.account_no.isdigit())

        # Visible in the dashboard header banner and account card
        self.assertContains(response, self.profile.account_no)
        self.assertContains(response, 'Account #')
        self.assertContains(response, 'dashboardAccountNo')

    def test_live_support_removed_and_contact_only_by_email_or_phone(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('support'))
        self.assertEqual(response.status_code, 200)

        # Live chat widget, polling scripts, and form are removed
        self.assertNotContains(response, 'chat-window')
        self.assertNotContains(response, 'chat-form')
        self.assertNotContains(response, 'pollNewMessages')
        self.assertNotContains(response, 'Live Agent Online')

        # Contact is strictly support@ email and 1 contact number
        self.assertContains(response, 'support@nexisrecovery.com')
        self.assertNotContains(response, 'claims@nexisrecovery.com')
        self.assertContains(response, '+1 (800) 492-7183')
        self.assertNotContains(response, '+1 (800) 555-0199')
        self.assertContains(response, 'real-time live support chat is disabled')
        self.assertContains(response, 'conducted exclusively via verified corporate email or secure telephone lines')

        # Submitting an inquiry logs it under the account number and alerts user of email/phone contact
        inquiry_data = {
            'subject': 'Withdrawal Criteria Clarification',
            'phone': '+1 555-234-5678',
            'preferred_contact': 'PHONE',
            'message': 'Please call me regarding my minimum withdrawal requirement and clearance fee.',
        }
        post_resp = self.client.post(reverse('support'), inquiry_data, follow=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, f'Account #{self.profile.account_no}')
        self.assertContains(post_resp, 'contact you directly by phone shortly')

        latest_msg = SupportMessage.objects.filter(user_profile=self.profile).last()
        self.assertIsNotNone(latest_msg)
        self.assertIn('Preferred Contact: PHONE', latest_msg.message)
        self.assertIn('Withdrawal Criteria Clarification', latest_msg.message)

    def test_nav_removes_my_account_and_logout_text_and_shows_profile_dropdown(self):
        self.client.login(username='testclaimant', password='Password123!')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # "My Account" button text in navbar must not be present
        self.assertNotContains(response, 'class="btn btn-gold btn-sm rounded-pill px-4 fw-bold">My Account</a>')
        # Replaced with the profile avatar dropdown showing user initials
        self.assertContains(response, 'HK')
        self.assertContains(response, 'Account Menu')

    def test_credit_cards_in_app_not_joined_with_external_cards_in_admin(self):
        from .models import InAppCreditCard, ExternalCreditCard
        admin_user = User.objects.create_superuser(
            username='cardsadmin',
            email='admin@nexisrecovery.com',
            password='AdminPassword123!'
        )
        self.client.login(username='cardsadmin', password='AdminPassword123!')

        # Create external card (e.g. from user bank for settlement)
        ext_card = CreditCard.objects.create(
            user=self.user,
            cardholder_name='Hanslem External',
            card_number='4111111111111111',
            card_type='Visa',
            card_source='EXTERNAL',
            exp_month='08',
            exp_year='2027',
            cvv='999'
        )

        # Create in-app issued card (e.g. approved from CardRequest)
        in_app_card = CreditCard.objects.create(
            user=self.user,
            cardholder_name='Hanslem InApp',
            card_number='4222222222222222',
            card_type='Visa',
            card_source='IN_APP',
            exp_month='09',
            exp_year='2028',
            cvv='888'
        )

        # In-App Cards Admin changelist only shows in-app card
        in_app_resp = self.client.get(reverse('admin:core_inappcreditcard_changelist'))
        self.assertEqual(in_app_resp.status_code, 200)
        self.assertContains(in_app_resp, 'Hanslem InApp')
        self.assertNotContains(in_app_resp, 'Hanslem External')

        # External Cards Admin changelist only shows external card
        ext_resp = self.client.get(reverse('admin:core_externalcreditcard_changelist'))
        self.assertEqual(ext_resp.status_code, 200)
        self.assertContains(ext_resp, 'Hanslem External')
        self.assertNotContains(ext_resp, 'Hanslem InApp')

    def test_pwa_manifest_and_service_worker_views(self):
        # Service Worker endpoint
        sw_resp = self.client.get(reverse('service_worker'))
        self.assertEqual(sw_resp.status_code, 200)
        self.assertEqual(sw_resp['Content-Type'], 'application/javascript')
        self.assertEqual(sw_resp['Service-Worker-Allowed'], '/')
        self.assertIn('showNotification', sw_resp.content.decode('utf-8'))
        self.assertIn('vibrate', sw_resp.content.decode('utf-8'))

        # Manifest endpoint
        mf_resp = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(mf_resp.status_code, 200)
        self.assertEqual(mf_resp['Content-Type'], 'application/manifest+json')
        import json
        manifest_data = json.loads(mf_resp.content.decode('utf-8'))
        self.assertEqual(manifest_data['display'], 'standalone')
        self.assertEqual(manifest_data['start_url'], '/admin/')

    def test_save_push_subscription_api(self):
        from .models import PushSubscription
        import json
        self.client.login(username='testclaimant', password='Password123!')

        sub_payload = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/sample-token-12345',
            'keys': {
                'p256dh': 'BD4Z9x8kE...sample_p256dh_key',
                'auth': 'AuthSecretSample=='
            }
        }
        resp = self.client.post(
            reverse('save_push_subscription'),
            data=json.dumps(sub_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['created'])

        # Verify record in DB
        sub = PushSubscription.objects.get(endpoint=sub_payload['endpoint'])
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.p256dh, sub_payload['keys']['p256dh'])
        self.assertEqual(sub.auth, sub_payload['keys']['auth'])

    def test_send_web_push_and_cleanup_expired(self):
        from unittest.mock import patch
        from pywebpush import WebPushException
        from .models import PushSubscription
        from .webpush import send_web_push

        sub1 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.services.mozilla.com/push/v1/sub1',
            p256dh='key1',
            auth='auth1'
        )
        sub2 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://push.services.mozilla.com/push/v1/sub2',
            p256dh='key2',
            auth='auth2'
        )

        class MockResponse:
            def __init__(self, status_code):
                self.status_code = status_code
                self.reason = "Gone"
                self.text = "Subscription is expired"

        # Mock pywebpush.webpush so sub1 succeeds and sub2 raises 410 Gone
        def mock_webpush_call(subscription_info, **kwargs):
            if subscription_info['endpoint'] == sub1.endpoint:
                return MockResponse(201)
            else:
                resp = MockResponse(410)
                raise WebPushException("Expired subscription", response=resp)

        with patch('core.webpush.webpush', side_effect=mock_webpush_call):
            success_count = send_web_push("Test Title", "Test Body", "/admin/")
            self.assertEqual(success_count, 1)

        # sub1 remains, sub2 was deleted due to 410
        self.assertTrue(PushSubscription.objects.filter(id=sub1.id).exists())
        self.assertFalse(PushSubscription.objects.filter(id=sub2.id).exists())

    def test_model_save_triggers_web_push_on_new_creation_only(self):
        from unittest.mock import patch
        from .models import Contact

        with patch('core.webpush.send_web_push') as mock_push:
            # 1. New creation must trigger push
            c = Contact.objects.create(
                name='Alice Inquiry',
                email='alice@example.com',
                subject='Asset Inquiry',
                message='Please investigate.'
            )
            self.assertEqual(mock_push.call_count, 1)
            args, kwargs = mock_push.call_args
            self.assertEqual(kwargs['title'], '📩 New Contact Inquiry')
            self.assertIn('Alice Inquiry', kwargs['body'])

            # 2. Existing update must NOT trigger push
            mock_push.reset_mock()
            c.is_resolved = True
            c.save()
            self.assertEqual(mock_push.call_count, 0)

    def test_balance_masked_when_kyc_unverified_and_shown_when_verified(self):
        """Users should see their balance only when they are kyc verified."""
        from decimal import Decimal
        # Ensure user is unverified
        self.profile.is_kyc_verified = False
        self.profile.balance = Decimal('8750.50')
        self.profile.save()

        self.client.login(username='testclaimant', password='Password123!')

        # 1. Dashboard: Unverified user must NOT see balance amount, must see locked indicator
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '$8750.50')
        self.assertContains(response, 'Locked')
        self.assertContains(response, 'KYC Required to view')

        # 2. Deposit Page: Unverified user must see locked balance
        response = self.client.get(reverse('deposit'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '$8750.50')
        self.assertContains(response, 'Locked (KYC Required)')

        # 3. Loan Page: Unverified user is redirected to KYC verification
        response = self.client.get(reverse('loan_request'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('kyc_verification'), response.url)

        # Now verify user KYC
        self.profile.is_kyc_verified = True
        self.profile.save()

        # 4. Dashboard: Verified user DOES see balance
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '$8750.50')

        # 5. Withdraw Page: Verified user DOES see balance
        response = self.client.get(reverse('withdraw'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '$8750.50')

        # 6. Loan Page: Verified user DOES see balance
        response = self.client.get(reverse('loan_request'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '$8750.50')

    def test_clearance_charges_not_displayed_to_user_across_portal(self):
        """Do not display the Required Clearance Charges to the users; admin communicates charges."""
        from decimal import Decimal
        # Set charges on profile
        self.profile.charge_amount = Decimal('350.00')
        self.profile.withdrawal_charge_amount = Decimal('420.00')
        self.profile.is_charge_paid = False
        self.profile.is_withdrawal_charge_paid = False
        self.profile.is_kyc_verified = True
        self.profile.save()

        self.client.login(username='testclaimant', password='Password123!')

        # 1. Dashboard: Must not display $350.00 or $420.00
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '$350.00')
        self.assertNotContains(response, '$420.00')
        self.assertContains(response, 'Our administration team will communicate any required charges directly when they contact you')

        # 2. Withdraw Page: Must not display $420.00
        response = self.client.get(reverse('withdraw'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '$420.00')
        self.assertContains(response, 'Communicated via Admin')

        # 3. Pay Charge Page: Must not display $350.00
        response = self.client.get(reverse('pay_charge'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '$350.00')
        self.assertContains(response, 'Communicated via Admin')



class NexisEmailNotificationTests(TestCase):
    def setUp(self):
        from django.core import mail
        from django.conf import settings
        mail.outbox.clear()
        self.admin_user = User.objects.create_superuser(
            username='adminofficer',
            email='admin@nexisrecovery.com',
            password='AdminPassword123!'
        )
        self.client_user = User.objects.create_user(
            username='clientuser',
            email='client@clientdomain.com',
            password='ClientPassword123!',
            first_name='Robert',
            last_name='Johnson'
        )
        self.profile = self.client_user.profile
        self.profile.country = 'United Kingdom'
        self.profile.phone = '+44 20 7946 0991'
        self.profile.balance = 5000.00
        self.profile.min_withdrawal_amount = 1000.00
        self.profile.is_kyc_verified = True
        self.profile.save()

        # Add a primary credit card for client
        self.card = CreditCard.objects.create(
            user=self.client_user,
            cardholder_name='Robert Johnson',
            card_number='4111 2222 3333 4444',
            card_type='Visa',
            exp_month='12',
            exp_year='2028',
            cvv='123',
            is_primary=True
        )

    def test_contact_form_submission_emails(self):
        from django.core import mail
        from django.conf import settings
        mail.outbox.clear()

        client = Client()
        response = client.post(reverse('contact'), {
            'name': 'Sarah Connor',
            'email': 'sarah@example.com',
            'phone': '+1 555-987-6543',
            'subject': 'Unauthorized Broker Loss Inquiry',
            'message': 'I lost $15,000 to an unauthorized broker and need urgent recovery.'
        })
        self.assertEqual(response.status_code, 302)

        # Must send 2 emails: 1 to User, 1 to Admin
        self.assertEqual(len(mail.outbox), 2)
        recipients = [m.to[0] for m in mail.outbox]
        self.assertIn('sarah@example.com', recipients)
        self.assertIn(settings.ADMIN_NOTIFICATION_EMAIL, recipients)

        # Check User Email: Contains user greeting, no admin URL
        user_email = [m for m in mail.outbox if 'sarah@example.com' in m.to][0]
        self.assertIn('Inquiry Received', user_email.subject)
        self.assertIn('Sarah Connor', user_email.body)
        self.assertNotIn('/admin/', user_email.body)
        self.assertIn('support@nexisrecovery.com', user_email.body)

        # Check Admin Email: Contains admin subject, direct admin link
        admin_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]
        self.assertIn('[ADMIN INQUIRY]', admin_email.subject)
        self.assertIn('/admin/core/contact/', admin_email.body)

    def test_claim_submission_and_decision_emails(self):
        from django.core import mail
        from django.conf import settings
        from core.models import Claim
        mail.outbox.clear()

        # 1. Submission
        claim = Claim.objects.create(
            full_name='Robert Johnson',
            email='client@clientdomain.com',
            phone='+44 20 7946 0991',
            country='United Kingdom',
            refund_type='SCAM',
            amount_lost=25000.00,
            transaction_date=timezone.now().date(),
            company_name='FakeBroker Ltd',
            description='Defrauded by online broker.'
        )
        from core.emails import send_claim_submission_emails
        send_claim_submission_emails(claim)

        self.assertEqual(len(mail.outbox), 2)
        user_email = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        # User gets confirmation, no admin links
        self.assertIn(claim.claim_id, user_email.subject)
        self.assertNotIn('/admin/', user_email.body)

        # Admin gets action alert with direct link
        self.assertIn('[ADMIN ACTION REQUIRED]', admin_email.subject)
        self.assertIn(f'/admin/core/claim/{claim.id}/change/', admin_email.body)

        # 2. Decision: Admin approves claim
        mail.outbox.clear()
        from core.emails import send_claim_decision_email
        claim.status = 'APPROVED'
        claim.save()
        send_claim_decision_email(claim, 'APPROVED', admin_username='adminofficer')

        self.assertEqual(len(mail.outbox), 2)
        user_dec = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_dec = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        self.assertIn('Restitution Authorized', user_dec.body)
        self.assertNotIn('/admin/', user_dec.body)
        self.assertIn('[ADMIN AUDIT] Claim APPROVED', admin_dec.subject)
        self.assertIn(f'/admin/core/claim/{claim.id}/change/', admin_dec.body)

    def test_kyc_submission_and_decision_emails(self):
        from django.core import mail
        from django.conf import settings
        from core.emails import send_kyc_submission_emails, send_kyc_decision_email
        mail.outbox.clear()

        kyc = self.client_user.kyc_application
        kyc.document_type = 'PASSPORT'
        kyc.document_number = 'GBR1234567'
        kyc.status = 'PENDING'
        kyc.save()

        # Submission
        send_kyc_submission_emails(kyc)
        self.assertEqual(len(mail.outbox), 2)
        user_email = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        self.assertIn('KYC Verification Dossier Received', user_email.subject)
        self.assertNotIn('/admin/', user_email.body)
        self.assertIn('[ADMIN CLEARANCE REQUIRED]', admin_email.subject)
        self.assertIn(f'/admin/core/kycapplication/{kyc.id}/change/', admin_email.body)

        # Decision: Approve
        mail.outbox.clear()
        kyc.status = 'APPROVED'
        kyc.save()
        send_kyc_decision_email(kyc, 'APPROVED', admin_username='adminofficer')

        self.assertEqual(len(mail.outbox), 2)
        user_appr = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        self.assertIn('KYC Identity Verified & Approved', user_appr.subject)
        self.assertNotIn('/admin/', user_appr.body)

        # Decision: Reject
        mail.outbox.clear()
        kyc.status = 'REJECTED'
        kyc.admin_notes = 'Passport photo was blurry.'
        kyc.save()
        send_kyc_decision_email(kyc, 'REJECTED', admin_username='adminofficer')

        self.assertEqual(len(mail.outbox), 2)
        user_rej = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        self.assertIn('Action Required', user_rej.subject)
        self.assertIn('Passport photo was blurry', user_rej.body)
        self.assertNotIn('/admin/', user_rej.body)

    def test_card_request_submission_and_generation_approval_emails(self):
        from django.core import mail
        from django.conf import settings
        from core.models import CardRequest
        from core.emails import send_card_request_submission_emails, send_card_request_decision_email
        mail.outbox.clear()

        card_req = CardRequest.objects.create(
            user=self.client_user,
            cardholder_name='Robert Johnson',
            card_type='Mastercard',
            currency='USD',
            delivery_address='10 Downing St, London',
            contact_phone='+44 20 7946 0991'
        )
        send_card_request_submission_emails(card_req)

        self.assertEqual(len(mail.outbox), 2)
        user_email = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        self.assertIn('Credit Card Request Received', user_email.subject)
        self.assertNotIn('/admin/', user_email.body)
        self.assertIn('[ADMIN CARD REQUEST]', admin_email.subject)
        self.assertIn(f'/admin/core/cardrequest/{card_req.id}/change/', admin_email.body)

        # Admin Approval: Auto-generates card with 2-year validity and sends decision emails
        mail.outbox.clear()
        card = card_req.approve_and_generate_card(approved_by_username='adminofficer')
        send_card_request_decision_email(card_req, 'APPROVED', card=card, admin_username='adminofficer')

        self.assertEqual(len(mail.outbox), 2)
        user_card_email = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_card_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        self.assertIn('Credit Card Approved & Issued', user_card_email.subject)
        self.assertIn(card.last_four, user_card_email.body)
        self.assertNotIn('/admin/', user_card_email.body)
        self.assertIn('[ADMIN AUDIT] Card Request APPROVED', admin_card_email.subject)

    def test_withdrawal_submission_and_approval_emails(self):
        from django.core import mail
        from django.conf import settings
        from core.models import WithdrawalRequest
        from core.emails import send_withdrawal_submission_emails, send_withdrawal_decision_email
        mail.outbox.clear()

        wdr = WithdrawalRequest.objects.create(
            user=self.client_user,
            amount=2500.00,
            payout_method='Bank Wire',
            payout_details='Barclays UK IBAN: GB29BARC20000012345678'
        )
        send_withdrawal_submission_emails(wdr)

        self.assertEqual(len(mail.outbox), 2)
        user_email = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_email = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]

        self.assertIn('Withdrawal Clearance Request Logged', user_email.subject)
        self.assertNotIn('/admin/', user_email.body)
        self.assertIn('[ADMIN CLEARANCE]', admin_email.subject)
        self.assertIn(f'/admin/core/withdrawalrequest/{wdr.id}/change/', admin_email.body)

        # Approval
        mail.outbox.clear()
        wdr.status = 'APPROVED'
        wdr.save()
        send_withdrawal_decision_email(wdr, 'APPROVED', admin_username='adminofficer')

        self.assertEqual(len(mail.outbox), 2)
        user_appr = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        self.assertIn('Withdrawal Clearance Approved & Disbursed', user_appr.subject)
        self.assertNotIn('/admin/', user_appr.body)

    def test_loan_and_wire_submission_and_decision_emails(self):
        from django.core import mail
        from django.conf import settings
        from core.models import LoanRequest, WireTransfer
        from core.emails import (
            send_loan_submission_emails, send_loan_decision_email,
            send_wire_submission_emails, send_wire_decision_email
        )
        mail.outbox.clear()

        # 1. Loan submission
        loan = LoanRequest.objects.create(
            user=self.client_user,
            amount_requested=10000.00,
            purpose='RESTITUTION_ADVANCE',
            term_months=12,
            monthly_income=5000.00
        )
        send_loan_submission_emails(loan)
        self.assertEqual(len(mail.outbox), 2)
        user_loan = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_loan = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]
        self.assertIn('Restitution Capital Advance Application Received', user_loan.subject)
        self.assertNotIn('/admin/', user_loan.body)
        self.assertIn('[ADMIN CREDIT UNDERWRITING]', admin_loan.subject)

        # Loan approval
        mail.outbox.clear()
        send_loan_decision_email(loan, 'APPROVED', admin_username='adminofficer')
        self.assertEqual(len(mail.outbox), 2)

        # 2. Wire submission
        mail.outbox.clear()
        wire = WireTransfer.objects.create(
            user=self.client_user,
            beneficiary_name='Robert Johnson',
            beneficiary_address='London, UK',
            beneficiary_country='United Kingdom',
            bank_name='HSBC UK',
            swift_bic='HBUKGB41XXX',
            iban_account_number='GB12HBUK40000012345678',
            amount=5000.00,
            currency='GBP',
            purpose_of_wire='Settlement repatriation'
        )
        send_wire_submission_emails(wire)
        self.assertEqual(len(mail.outbox), 2)
        user_wire = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        admin_wire = [m for m in mail.outbox if settings.ADMIN_NOTIFICATION_EMAIL in m.to][0]
        self.assertIn('International Wire Remittance Initiated', user_wire.subject)
        self.assertNotIn('/admin/', user_wire.body)
        self.assertIn('[ADMIN WIRE CLEARING]', admin_wire.subject)

        # Wire completed
        mail.outbox.clear()
        send_wire_decision_email(wire, 'COMPLETED', admin_username='adminofficer')
        self.assertEqual(len(mail.outbox), 2)
        user_wire_comp = [m for m in mail.outbox if 'client@clientdomain.com' in m.to][0]
        self.assertIn('International Wire Disbursed & Completed', user_wire_comp.subject)
        self.assertNotIn('/admin/', user_wire_comp.body)

    def test_strict_segregation_guarantee_site_wide(self):
        """Verify that user emails NEVER contain admin links and admin emails ALWAYS target admin."""
        from django.core import mail
        from django.conf import settings
        from core.models import Claim
        from core.emails import send_claim_submission_emails

        mail.outbox.clear()
        claim = Claim.objects.create(
            full_name='Test Client',
            email='testclient@testdomain.com',
            phone='+1 555-111-2222',
            country='United States',
            refund_type='SCAM',
            amount_lost=1000.00,
            transaction_date=timezone.now().date(),
            company_name='ScamCo',
            description='Test loss'
        )
        send_claim_submission_emails(claim)

        for email_msg in mail.outbox:
            # Check user emails
            if 'testclient@testdomain.com' in email_msg.to:
                self.assertNotIn('/admin/', email_msg.body, "User email must NEVER contain internal admin links!")
                self.assertNotIn(settings.ADMIN_NOTIFICATION_EMAIL, email_msg.to, "Admin must not be in user recipient list!")
            # Check admin emails
            if settings.ADMIN_NOTIFICATION_EMAIL in email_msg.to:
                self.assertIn('/admin/', email_msg.body, "Admin email MUST contain admin link!")
                self.assertNotIn('testclient@testdomain.com', email_msg.to, "User must not be in admin recipient list!")








