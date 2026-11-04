import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = "support@nexisrecovery.com"
SUPPORT_PHONE = "+1 (555) 123-4567"

def get_site_url():
    return getattr(settings, 'SITE_URL', 'https://nexisrecovery.com').rstrip('/')

def send_html_email(subject, template_name, context, recipient_list, is_admin=False):
    """
    Renders and sends a professional responsive HTML corporate email with plain-text fallback.
    Guarantees strict segregation:
    - User emails receive user templates and client portal URLs.
    - Admin emails receive admin templates and Django admin URLs.
    """
    if not recipient_list:
        logger.warning(f"No recipients specified for email '{subject}'. Skipping dispatch.")
        return False

    # Filter out empty or whitespace strings
    clean_recipients = [r.strip() for r in recipient_list if r and r.strip()]
    if not clean_recipients:
        return False

    site_url = get_site_url()
    base_context = {
        'site_url': site_url,
        'support_email': SUPPORT_EMAIL,
        'support_phone': SUPPORT_PHONE,
        'current_year': timezone.now().year,
        'is_admin': is_admin,
    }
    base_context.update(context)

    try:
        html_content = render_to_string(template_name, base_context)
        text_content = strip_tags(html_content)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', f'Nexis Cyber Recovery <{SUPPORT_EMAIL}>')

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=clean_recipients
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        logger.info(f"Successfully sent {'ADMIN' if is_admin else 'USER'} email '{subject}' to {clean_recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {clean_recipients}: {e}", exc_info=True)
        return False


# =========================================================================
# SUBMISSION DISPATCHERS
# =========================================================================

def send_claim_submission_emails(claim):
    """Dispatches separate emails upon a new claim submission."""
    site_url = get_site_url()
    event_date = claim.created_at.strftime('%B %d, %Y')

    # 1. User Confirmation Email
    user_context = {
        'email_subject': f"Case Confirmation: Claim #{claim.claim_id} Lodged",
        'preheader': f"Your recovery claim #{claim.claim_id} has been securely registered with Nexis.",
        'status_label': 'CLAIM LODGED & SECURED',
        'status_color': 'info',
        'heading': f"Recovery Claim #{claim.claim_id} Confirmed",
        'reference_id': claim.claim_id,
        'event_date': event_date,
        'recipient_name': claim.full_name,
        'message_body': (
            f"Thank you for submitting your dispute dossier to <strong>Nexis Cyber Recovery</strong>. "
            f"Your case file has been assigned a priority tracking docket and is now undergoing forensic audit "
            f"by our specialized recovery department."
        ),
        'details': [
            {'label': 'Docket Reference', 'value': claim.claim_id},
            {'label': 'Claimant Name', 'value': claim.full_name},
            {'label': 'Disputed Merchant / Entity', 'value': claim.company_name},
            {'label': 'Claim Category', 'value': claim.get_refund_type_display()},
            {'label': 'Amount in Dispute', 'value': f"${claim.amount_lost:,.2f} USD"},
            {'label': 'Incident / Transaction Date', 'value': str(claim.transaction_date)},
            {'label': 'Initial Status', 'value': 'Pending Review & Verification'},
        ],
        'extra_note': (
            "Our forensic analysts may contact you if supplementary documentary evidence (such as wire receipts or communications) "
            "is required to strengthen your case against the merchant or banking institution."
        ),
        'cta_url': f"{site_url}/claim-status/",
        'cta_text': "Track Claim Status",
    }
    send_html_email(
        subject=f"Case Confirmation: Claim #{claim.claim_id} Lodged",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[claim.email],
        is_admin=False
    )

    # 2. Admin Operational Notification Email
    admin_context = {
        'email_subject': f"[ADMIN ACTION REQUIRED] New Claim Submission #{claim.claim_id}",
        'preheader': f"New ${claim.amount_lost:,.2f} dispute claim submitted by {claim.full_name}.",
        'status_label': 'NEW CLAIM SUBMISSION',
        'heading': f"New Case File Lodged: #{claim.claim_id}",
        'reference_id': claim.claim_id,
        'event_date': event_date,
        'message_body': (
            f"A new restitution claim has been filed on the public portal. "
            f"The dossier requires initial evidence verification and investigator assignment."
        ),
        'details': [
            {'label': 'Claim ID', 'value': claim.claim_id},
            {'label': 'Applicant Full Name', 'value': claim.full_name},
            {'label': 'Email Address', 'value': claim.email},
            {'label': 'Phone Number', 'value': claim.phone},
            {'label': 'Country', 'value': claim.country},
            {'label': 'Merchant / Entity', 'value': claim.company_name},
            {'label': 'Loss Category', 'value': claim.get_refund_type_display()},
            {'label': 'Amount Claimed', 'value': f"${claim.amount_lost:,.2f} USD"},
            {'label': 'Proof File Attached', 'value': 'Yes' if claim.proof_file else 'No'},
        ],
        'extra_note': "Verify the uploaded proof against fraudulent duplicate submissions before initiating bank dispute filings.",
        'admin_url': f"{site_url}/admin/core/claim/{claim.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN ACTION REQUIRED] New Claim Submission #{claim.claim_id}",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_kyc_submission_emails(kyc):
    """Dispatches separate emails when a user submits their KYC verification application."""
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = kyc.user
    applicant_name = user.get_full_name() or user.username

    # 1. User Email
    user_context = {
        'email_subject': f"KYC Verification Dossier Received: {kyc.application_id}",
        'preheader': "Your identity verification documents have been received by our Compliance Department.",
        'status_label': 'KYC UNDER REVIEW',
        'status_color': 'warning',
        'heading': "Identity Verification Dossier Under Review",
        'reference_id': kyc.application_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': (
            f"Thank you for submitting your identity documents and settlement payment card for <strong>KYC verification</strong>. "
            f"Under international Anti-Money Laundering (AML) and financial regulatory guidelines, all client accounts must undergo "
            f"mandatory forensic identity clearance prior to transaction disbursement."
        ),
        'details': [
            {'label': 'Application Reference', 'value': kyc.application_id},
            {'label': 'Document Type', 'value': kyc.get_document_type_display()},
            {'label': 'Document Number', 'value': kyc.document_number or 'Provided in Upload'},
            {'label': 'Jurisdiction', 'value': kyc.country or (user.profile.country if hasattr(user, 'profile') else 'International')},
            {'label': 'Card Attached', 'value': f"{kyc.credit_card.card_type} •••• {kyc.credit_card.last_four}" if kyc.credit_card else 'Under File'},
            {'label': 'Review Status', 'value': 'Pending Compliance Clearance'},
        ],
        'extra_note': (
            "A statutory KYC forensic verification and regulatory clearance fee is required to finalize authentication. "
            "Our compliance administration team will contact you directly via your registered email or phone number with instructions. "
            "Your application is locked under review and cannot be re-submitted until an administrator approves or rejects it."
        ),
        'cta_url': f"{site_url}/accounts/kyc/",
        'cta_text': "View KYC Dossier Status",
    }
    send_html_email(
        subject=f"KYC Verification Dossier Received: {kyc.application_id}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN CLEARANCE REQUIRED] New KYC Dossier #{kyc.application_id} ({user.username})",
        'preheader': f"KYC documents submitted by {applicant_name} ({user.username}). Action required.",
        'status_label': 'KYC CLEARANCE REQUIRED',
        'heading': f"New KYC Verification Dossier: #{kyc.application_id}",
        'reference_id': kyc.application_id,
        'event_date': event_date,
        'message_body': (
            f"Client <strong>{applicant_name}</strong> (Username: <code>{user.username}</code>) has submitted their "
            f"statutory identification documents and settlement card. The dossier requires forensic document inspection and "
            f"statutory fee assignment."
        ),
        'details': [
            {'label': 'KYC Reference', 'value': kyc.application_id},
            {'label': 'Client Username', 'value': user.username},
            {'label': 'Client Legal Name', 'value': applicant_name},
            {'label': 'Email Address', 'value': user.email},
            {'label': 'Phone Number', 'value': kyc.phone_number or (user.profile.phone if hasattr(user, 'profile') else 'N/A')},
            {'label': 'Account Number', 'value': user.profile.account_no if hasattr(user, 'profile') else 'N/A'},
            {'label': 'Document Type', 'value': kyc.get_document_type_display()},
            {'label': 'Document Number', 'value': kyc.document_number or 'Uploaded'},
            {'label': 'Document Expiry', 'value': str(kyc.document_expiry) if kyc.document_expiry else 'Not Specified'},
            {'label': 'Settlement Card Linked', 'value': f"{kyc.credit_card.card_type} •••• {kyc.credit_card.last_four}" if kyc.credit_card else 'None'},
        ],
        'extra_note': "Verify identity documents against AML watchlist. Set the required clearance charge or proceed with approval/rejection.",
        'admin_url': f"{site_url}/admin/core/kycapplication/{kyc.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN CLEARANCE REQUIRED] New KYC Dossier #{kyc.application_id}",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_card_request_submission_emails(card_request):
    """Dispatches separate emails when a user submits a Credit Card issuance request."""
    site_url = get_site_url()
    event_date = card_request.requested_at.strftime('%B %d, %Y')
    user = card_request.user
    applicant_name = card_request.cardholder_name or user.get_full_name() or user.username

    # 1. User Email
    user_context = {
        'email_subject': f"Credit Card Request Received: Ref #{card_request.request_id}",
        'preheader': f"Your application for a {card_request.card_type} card has been lodged.",
        'status_label': 'CARD REQUEST LODGED',
        'status_color': 'info',
        'heading': f"Restitution Card Request: Ref #{card_request.request_id}",
        'reference_id': card_request.request_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': (
            f"Your requisition for an official <strong>{card_request.card_type}</strong> restitution card has been "
            f"received by the Nexis Treasury and Card Administration Desk."
        ),
        'details': [
            {'label': 'Requisition Reference', 'value': card_request.request_id},
            {'label': 'Cardholder Legal Name', 'value': card_request.cardholder_name},
            {'label': 'Card Type Requested', 'value': card_request.get_card_type_display()},
            {'label': 'Billing Currency', 'value': card_request.get_currency_display()},
            {'label': 'Contact Phone', 'value': card_request.contact_phone or 'On File'},
            {'label': 'Validity Duration', 'value': '2 Years from Approval Date'},
            {'label': 'Status', 'value': 'Pending Administrative Approval'},
        ],
        'extra_note': (
            "Our card administration team will contact you via email or phone number regarding the required card issuance and dispatch charges. "
            "Once approved, your card will be automatically generated with requester's name and a 2-year validity from the approval date."
        ),
        'cta_url': f"{site_url}/accounts/my-cards/",
        'cta_text': "View My Cards Portal",
    }
    send_html_email(
        subject=f"Credit Card Request Received: Ref #{card_request.request_id}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN CARD REQUEST] #{card_request.request_id} ({card_request.card_type})",
        'preheader': f"New credit card request from {applicant_name} ({user.username}).",
        'status_label': 'CARD ISSUANCE REQUEST',
        'heading': f"New Card Requisition: #{card_request.request_id}",
        'reference_id': card_request.request_id,
        'event_date': event_date,
        'message_body': (
            f"User <strong>{user.username}</strong> ({applicant_name}) has requested issuance of a "
            f"<strong>{card_request.card_type}</strong>. Upon administrative approval, the system will automatically "
            f"generate the 16-digit card with 2-year validity expiring from the approval date."
        ),
        'details': [
            {'label': 'Request ID', 'value': card_request.request_id},
            {'label': 'Applicant Username', 'value': user.username},
            {'label': 'Cardholder Legal Name', 'value': card_request.cardholder_name},
            {'label': 'Applicant Email', 'value': user.email},
            {'label': 'Contact Phone', 'value': card_request.contact_phone},
            {'label': 'Card Program', 'value': card_request.card_type},
            {'label': 'Currency', 'value': card_request.currency},
            {'label': 'Delivery Address', 'value': card_request.delivery_address or 'Not specified'},
        ],
        'extra_note': "Verify KYC standing and assess issuance fee before approving. Approving will automatically generate and issue the card.",
        'admin_url': f"{site_url}/admin/core/cardrequest/{card_request.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN CARD REQUEST] #{card_request.request_id} ({card_request.card_type})",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_withdrawal_submission_emails(withdrawal):
    """Dispatches separate emails when a user submits a withdrawal inquiry."""
    site_url = get_site_url()
    event_date = withdrawal.created_at.strftime('%B %d, %Y')
    user = withdrawal.user
    applicant_name = user.get_full_name() or user.username
    profile = getattr(user, 'profile', None)

    # 1. User Email
    user_context = {
        'email_subject': f"Withdrawal Clearance Request Logged: #{withdrawal.request_id}",
        'preheader': f"Your withdrawal request for ${withdrawal.amount:,.2f} is being reviewed.",
        'status_label': 'WITHDRAWAL IN REVIEW',
        'status_color': 'warning',
        'heading': f"Withdrawal Clearance Request: #{withdrawal.request_id}",
        'reference_id': withdrawal.request_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': (
            f"We have received your fund withdrawal clearance request for <strong>${withdrawal.amount:,.2f} USD</strong>. "
            f"Your request has been routed to our settlement department for balance verification and regulatory clearance."
        ),
        'details': [
            {'label': 'Request Reference', 'value': withdrawal.request_id},
            {'label': 'Requested Amount', 'value': f"${withdrawal.amount:,.2f} USD"},
            {'label': 'Payout Method', 'value': withdrawal.payout_method},
            {'label': 'Current Balance', 'value': (f"${profile.balance:,.2f} USD" if (profile and profile.is_kyc_verified) else 'Locked (KYC Required)')},
            {'label': 'Min Withdrawal Threshold', 'value': f"${profile.min_withdrawal_amount:,.2f} USD" if profile else 'N/A'},
            {'label': 'Status', 'value': 'Pending Administrative Clearance'},
        ],
        'extra_note': (
            "Please ensure your KYC identity verification and any statutory clearance charges are cleared. "
            "Our administration team will contact you directly to finalize disbursement authorization."
        ),
        'cta_url': f"{site_url}/accounts/withdraw/",
        'cta_text': "View Withdrawal Status",
    }
    send_html_email(
        subject=f"Withdrawal Clearance Request Logged: #{withdrawal.request_id}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN CLEARANCE] New Withdrawal Request #{withdrawal.request_id} (${withdrawal.amount:,.2f})",
        'preheader': f"User {user.username} requested ${withdrawal.amount:,.2f} withdrawal.",
        'status_label': 'WITHDRAWAL CLEARANCE REQUIRED',
        'heading': f"Withdrawal Clearance Order: #{withdrawal.request_id}",
        'reference_id': withdrawal.request_id,
        'event_date': event_date,
        'message_body': (
            f"Client <strong>{user.username}</strong> ({applicant_name}) has submitted a request to withdraw "
            f"<strong>${withdrawal.amount:,.2f} USD</strong>."
        ),
        'details': [
            {'label': 'Request ID', 'value': withdrawal.request_id},
            {'label': 'Username', 'value': user.username},
            {'label': 'Account Number', 'value': profile.account_no if profile else 'N/A'},
            {'label': 'Current Balance', 'value': f"${profile.balance:,.2f} USD" if profile else 'N/A'},
            {'label': 'Min Threshold', 'value': f"${profile.min_withdrawal_amount:,.2f} USD" if profile else 'N/A'},
            {'label': 'Requested Amount', 'value': f"${withdrawal.amount:,.2f} USD"},
            {'label': 'Payout Method', 'value': withdrawal.payout_method},
            {'label': 'Payout Details', 'value': withdrawal.payout_details},
            {'label': 'KYC Verified', 'value': 'Yes' if profile and profile.is_kyc_verified else 'NO - Action Needed'},
            {'label': 'Clearance Charge Paid', 'value': 'Yes' if profile and profile.is_withdrawal_charge_paid else 'NO'},
        ],
        'extra_note': "Verify that the user balance satisfies the Minimum Withdrawal Requirement and that clearance charges are collected prior to disbursement.",
        'admin_url': f"{site_url}/admin/core/withdrawalrequest/{withdrawal.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN CLEARANCE] New Withdrawal Request #{withdrawal.request_id} (${withdrawal.amount:,.2f})",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_wire_submission_emails(wire):
    """Dispatches separate emails when a user submits an International Wire transfer."""
    site_url = get_site_url()
    event_date = wire.created_at.strftime('%B %d, %Y')
    user = wire.user
    applicant_name = user.get_full_name() or user.username

    # 1. User Email
    user_context = {
        'email_subject': f"International Wire Remittance Initiated: Ref #{wire.reference_id}",
        'preheader': f"Your international wire transfer for {wire.currency} {wire.amount:,.2f} has been registered.",
        'status_label': 'WIRE INITIATED',
        'status_color': 'info',
        'heading': f"International Wire Dossier: #{wire.reference_id}",
        'reference_id': wire.reference_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': (
            f"Your international bank wire transfer instruction of <strong>{wire.currency} {wire.amount:,.2f}</strong> "
            f"payable to <strong>{wire.beneficiary_name}</strong> has been registered with our international clearing desk."
        ),
        'details': [
            {'label': 'Remittance Reference', 'value': wire.reference_id},
            {'label': 'Beneficiary Name', 'value': wire.beneficiary_name},
            {'label': 'Beneficiary Bank', 'value': wire.bank_name},
            {'label': 'SWIFT / BIC Code', 'value': wire.swift_bic},
            {'label': 'IBAN / Account Number', 'value': wire.iban_account_number},
            {'label': 'Remittance Amount', 'value': f"{wire.currency} {wire.amount:,.2f}"},
            {'label': 'Remittance Purpose', 'value': wire.purpose_of_wire},
            {'label': 'Status', 'value': 'Pending Clearing Review'},
        ],
        'extra_note': (
            "Cross-border restitution wires are cleared in accordance with SWIFT protocols. "
            "Our compliance and international clearing desk will review your instructions and contact you."
        ),
        'cta_url': f"{site_url}/accounts/international-wire/",
        'cta_text': "View Wire Status",
    }
    send_html_email(
        subject=f"International Wire Remittance Initiated: Ref #{wire.reference_id}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN WIRE CLEARING] New International Wire #{wire.reference_id} ({wire.currency} {wire.amount:,.2f})",
        'preheader': f"International wire transfer from {user.username} to {wire.beneficiary_name}.",
        'status_label': 'INTERNATIONAL WIRE ORDER',
        'heading': f"International Wire Order: #{wire.reference_id}",
        'reference_id': wire.reference_id,
        'event_date': event_date,
        'message_body': (
            f"Client <strong>{user.username}</strong> ({applicant_name}) has initiated a cross-border wire remittance "
            f"for <strong>{wire.currency} {wire.amount:,.2f}</strong>."
        ),
        'details': [
            {'label': 'Wire Reference', 'value': wire.reference_id},
            {'label': 'Originating User', 'value': user.username},
            {'label': 'User Email', 'value': user.email},
            {'label': 'Beneficiary Name', 'value': wire.beneficiary_name},
            {'label': 'Beneficiary Country', 'value': wire.beneficiary_country},
            {'label': 'Bank Name', 'value': wire.bank_name},
            {'label': 'SWIFT / BIC', 'value': wire.swift_bic},
            {'label': 'IBAN / Account', 'value': wire.iban_account_number},
            {'label': 'Amount / Currency', 'value': f"{wire.currency} {wire.amount:,.2f}"},
            {'label': 'Purpose', 'value': wire.purpose_of_wire},
        ],
        'extra_note': "Verify recipient banking details and perform sanctions screening before releasing funds through correspondent network.",
        'admin_url': f"{site_url}/admin/core/wiretransfer/{wire.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN WIRE CLEARING] New International Wire #{wire.reference_id} ({wire.currency} {wire.amount:,.2f})",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_loan_submission_emails(loan):
    """Dispatches separate emails when a user submits a loan / capital advance application."""
    site_url = get_site_url()
    event_date = loan.created_at.strftime('%B %d, %Y')
    user = loan.user
    applicant_name = user.get_full_name() or user.username

    # 1. User Email
    user_context = {
        'email_subject': f"Restitution Capital Advance Application Received: #{loan.loan_id}",
        'preheader': f"Your advance request for ${loan.amount_requested:,.2f} is under credit review.",
        'status_label': 'APPLICATION UNDER REVIEW',
        'status_color': 'info',
        'heading': f"Restitution Capital Advance: #{loan.loan_id}",
        'reference_id': loan.loan_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': (
            f"Your application for a Restitution Capital Advance of <strong>${loan.amount_requested:,.2f} USD</strong> "
            f"has been received by our credit committee. Our underwriting team is evaluating your application."
        ),
        'details': [
            {'label': 'Application Reference', 'value': loan.loan_id},
            {'label': 'Requested Capital', 'value': f"${loan.amount_requested:,.2f} USD"},
            {'label': 'Advance Facility Purpose', 'value': loan.get_purpose_display()},
            {'label': 'Term Duration', 'value': f"{loan.term_months} Months"},
            {'label': 'Annual Percentage Rate (APR)', 'value': f"{loan.annual_interest_rate}%"},
            {'label': 'Repayment Source', 'value': loan.repayment_source},
            {'label': 'Current Status', 'value': 'Under Credit & Forensic Review'},
        ],
        'extra_note': (
            "Our credit and underwriting committee will review your application within 24 to 48 hours. "
            "You will be notified once a determination is made."
        ),
        'cta_url': f"{site_url}/accounts/loan/",
        'cta_text': "View Loan Application",
    }
    send_html_email(
        subject=f"Restitution Capital Advance Application Received: #{loan.loan_id}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN CREDIT UNDERWRITING] New Loan Application #{loan.loan_id} (${loan.amount_requested:,.2f})",
        'preheader': f"Loan request from {user.username} for ${loan.amount_requested:,.2f}.",
        'status_label': 'CREDIT APPLICATION PENDING',
        'heading': f"New Loan Application: #{loan.loan_id}",
        'reference_id': loan.loan_id,
        'event_date': event_date,
        'message_body': (
            f"Client <strong>{user.username}</strong> ({applicant_name}) has submitted an underwriting request "
            f"for a Restitution Capital Advance of <strong>${loan.amount_requested:,.2f} USD</strong>."
        ),
        'details': [
            {'label': 'Loan Docket ID', 'value': loan.loan_id},
            {'label': 'Applicant Username', 'value': user.username},
            {'label': 'Applicant Email', 'value': user.email},
            {'label': 'Amount Requested', 'value': f"${loan.amount_requested:,.2f} USD"},
            {'label': 'Facility Purpose', 'value': loan.get_purpose_display()},
            {'label': 'Term Duration', 'value': f"{loan.term_months} Months"},
            {'label': 'Monthly Income', 'value': f"${loan.monthly_income:,.2f}"},
            {'label': 'Employment Status', 'value': loan.employment_status},
            {'label': 'Collateral Claim Ref', 'value': loan.collateral_claim_reference or 'None'},
        ],
        'extra_note': "Perform creditworthiness assessment and cross-reference with open claim files prior to approval.",
        'admin_url': f"{site_url}/admin/core/loanrequest/{loan.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN CREDIT UNDERWRITING] New Loan Application #{loan.loan_id} (${loan.amount_requested:,.2f})",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_contact_submission_emails(contact):
    """Dispatches separate emails when someone submits the Contact Us form."""
    site_url = get_site_url()
    event_date = contact.created_at.strftime('%B %d, %Y')

    # 1. User Acknowledgment Email
    user_context = {
        'email_subject': f"Inquiry Received - Nexis Cyber Recovery: {contact.subject}",
        'preheader': "Thank you for contacting Nexis Cyber Recovery. Your inquiry has been registered.",
        'status_label': 'INQUIRY RECEIVED',
        'status_color': 'info',
        'heading': "Thank You For Contacting Us",
        'reference_id': f"INQ-{contact.id:05d}",
        'event_date': event_date,
        'recipient_name': contact.name,
        'message_body': (
            f"We have received your inquiry regarding <strong>\"{contact.subject}\"</strong>. "
            f"A member of our client intake and case assessment team will review your message "
            f"and respond promptly."
        ),
        'details': [
            {'label': 'Inquiry Ticket', 'value': f"INQ-{contact.id:05d}"},
            {'label': 'Subject', 'value': contact.subject},
            {'label': 'Sender Name', 'value': contact.name},
            {'label': 'Sender Email', 'value': contact.email},
            {'label': 'Phone', 'value': contact.phone or 'Not Provided'},
        ],
        'extra_note': "Our general consultation team operates Monday through Saturday. For urgent case updates, please reply directly to this email.",
        'cta_url': f"{site_url}/",
        'cta_text': "Visit Nexis Cyber Recovery",
    }
    send_html_email(
        subject=f"Inquiry Received - Nexis Cyber Recovery: {contact.subject}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[contact.email],
        is_admin=False
    )

    # 2. Admin Alert Email
    admin_context = {
        'email_subject': f"[ADMIN INQUIRY] New Message from {contact.name}: {contact.subject}",
        'preheader': f"Contact form submission from {contact.name} ({contact.email}).",
        'status_label': 'NEW CONTACT INQUIRY',
        'heading': f"New Website Inquiry: {contact.subject}",
        'reference_id': f"INQ-{contact.id:05d}",
        'event_date': event_date,
        'message_body': (
            f"A visitor has submitted an inquiry through the public contact portal. Details are provided below:"
        ),
        'details': [
            {'label': 'Inquiry Reference', 'value': f"INQ-{contact.id:05d}"},
            {'label': 'Sender Name', 'value': contact.name},
            {'label': 'Sender Email', 'value': contact.email},
            {'label': 'Sender Phone', 'value': contact.phone or 'None'},
            {'label': 'Subject', 'value': contact.subject},
            {'label': 'Message Body', 'value': contact.message},
        ],
        'extra_note': "Review inquiry and initiate case intake or reply directly to the prospective client.",
        'admin_url': f"{site_url}/admin/core/contact/{contact.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN INQUIRY] New Message from {contact.name}: {contact.subject}",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


# =========================================================================
# APPROVAL & REJECTION (DECISION) DISPATCHERS
# =========================================================================

def send_kyc_decision_email(kyc, decision, admin_username='Compliance Officer'):
    """
    Dispatches determination notice when KYC is Approved or Rejected.
    decision: 'APPROVED' or 'REJECTED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = kyc.user
    applicant_name = user.get_full_name() or user.username
    is_approved = (decision == 'APPROVED')

    # 1. User Email
    if is_approved:
        user_subject = f"KYC Identity Verified & Approved: {kyc.application_id}"
        status_label = "KYC IDENTITY VERIFIED"
        status_color = "success"
        heading = "Congratulations! Your Account Identity Is Fully Verified"
        message_body = (
            f"We are pleased to inform you that your <strong>KYC verification application ({kyc.application_id})</strong> "
            f"has been formally <strong>APPROVED</strong> by our compliance and legal department. "
            f"All transaction features &mdash; including fund withdrawals, international wire orders, and card issuances &mdash; "
            f"are now activated on your account."
        )
        extra_note = "Your account now holds verified status with global restitution clearing privileges."
    else:
        user_subject = f"KYC Verification Notice: Action Required on {kyc.application_id}"
        status_label = "KYC STATUS: REJECTED"
        status_color = "danger"
        heading = "KYC Verification Update &mdash; Action Required"
        rejection_reason = kyc.admin_notes or "Document legibility or compliance validation criteria was not met."
        message_body = (
            f"Our compliance department has completed review of your KYC submission ({kyc.application_id}). "
            f"At this stage, your verification could not be approved due to the following reason:<br><br>"
            f"<strong>Compliance Notice:</strong> <em>{rejection_reason}</em><br><br>"
            f"Please log into your portal to review and update your identity documents."
        )
        extra_note = "If you believe this was an error or require assistance, please contact our compliance desk."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Important status update regarding your KYC verification {kyc.application_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': kyc.application_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': message_body,
        'details': [
            {'label': 'KYC Reference', 'value': kyc.application_id},
            {'label': 'Document Type', 'value': kyc.get_document_type_display()},
            {'label': 'Account Number', 'value': user.profile.account_no if hasattr(user, 'profile') else 'N/A'},
            {'label': 'Verification Outcome', 'value': 'APPROVED' if is_approved else 'REJECTED'},
            {'label': 'Reviewed Date', 'value': event_date},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/accounts/kyc/",
        'cta_text': "View My Account Status",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] KYC {decision}: #{kyc.application_id} ({user.username})"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"KYC {decision} for user {user.username} by {admin_username}.",
        'status_label': f"KYC AUDIT: {decision}",
        'heading': f"KYC Determination Executed: {decision}",
        'reference_id': kyc.application_id,
        'event_date': event_date,
        'message_body': (
            f"KYC Application <strong>#{kyc.application_id}</strong> for user <strong>{user.username}</strong> "
            f"has been marked as <strong>{decision}</strong> by administrator <strong>{admin_username}</strong>."
        ),
        'details': [
            {'label': 'Application ID', 'value': kyc.application_id},
            {'label': 'Client Username', 'value': user.username},
            {'label': 'Client Email', 'value': user.email},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Officer Username', 'value': admin_username},
            {'label': 'Notes / Reason', 'value': kyc.admin_notes or 'Standard verification protocol'},
        ],
        'extra_note': "Audit log recorded for compliance regulatory archives.",
        'admin_url': f"{site_url}/admin/core/kycapplication/{kyc.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_card_request_decision_email(card_request, decision, card=None, admin_username='Admin'):
    """
    Dispatches determination notice when a Credit Card Request is Approved or Rejected.
    decision: 'APPROVED' or 'REJECTED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = card_request.user
    applicant_name = card_request.cardholder_name or user.get_full_name() or user.username
    is_approved = (decision == 'APPROVED')
    card_obj = card or card_request.generated_card

    # 1. User Email
    if is_approved:
        user_subject = f"Credit Card Approved & Issued: Ref #{card_request.request_id}"
        status_label = "CARD APPROVED & ISSUED"
        status_color = "success"
        heading = f"Your {card_request.card_type} Has Been Issued!"
        masked = card_obj.masked_number if card_obj else "•••• •••• •••• Card Active"
        expiry = card_obj.expiry if card_obj else "2 Years"
        message_body = (
            f"We are delighted to confirm that your <strong>{card_request.card_type}</strong> request "
            f"(Ref: {card_request.request_id}) has been formally <strong>APPROVED</strong>. "
            f"Your card has been generated in your legal name <strong>{card_request.cardholder_name}</strong> "
            f"with a 2-year validity period expiring <strong>{expiry}</strong>."
        )
        extra_note = "You can view your active card credentials and manage settings inside your Client Portal under My Payment Cards."
    else:
        user_subject = f"Credit Card Request Update: Ref #{card_request.request_id}"
        status_label = "CARD REQUEST REJECTED"
        status_color = "danger"
        heading = "Credit Card Application Status Update"
        rejection_notes = card_request.admin_notes or "Issuance criteria or fee clearance requirement was not fulfilled."
        message_body = (
            f"Your request for a {card_request.card_type} (Ref: {card_request.request_id}) could not be completed at this time.<br><br>"
            f"<strong>Reason:</strong> <em>{rejection_notes}</em>"
        )
        extra_note = "If you have questions regarding this determination, please reach out to our card services desk."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Notice regarding your credit card request #{card_request.request_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': card_request.request_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': message_body,
        'details': [
            {'label': 'Request Reference', 'value': card_request.request_id},
            {'label': 'Card Program', 'value': card_request.card_type},
            {'label': 'Cardholder Name', 'value': card_request.cardholder_name},
            {'label': 'Card Number', 'value': card_obj.masked_number if card_obj else '•••• •••• •••• Active'},
            {'label': 'Expiry Validity', 'value': f"{card_obj.expiry} (2-Year Term)" if card_obj else '2 Years from Approval'},
            {'label': 'Decision', 'value': 'APPROVED & ACTIVE' if is_approved else 'REJECTED'},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/accounts/my-cards/",
        'cta_text': "View My Payment Cards",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] Card Request {decision}: #{card_request.request_id} ({user.username})"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"Card Request {decision} for user {user.username}.",
        'status_label': f"CARD AUDIT: {decision}",
        'heading': f"Credit Card Request Determination: {decision}",
        'reference_id': card_request.request_id,
        'event_date': event_date,
        'message_body': (
            f"Credit Card Request <strong>#{card_request.request_id}</strong> for user <strong>{user.username}</strong> "
            f"has been marked as <strong>{decision}</strong> by administrator <strong>{admin_username}</strong>."
        ),
        'details': [
            {'label': 'Request ID', 'value': card_request.request_id},
            {'label': 'Applicant Username', 'value': user.username},
            {'label': 'Applicant Email', 'value': user.email},
            {'label': 'Card Type', 'value': card_request.card_type},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Approved By', 'value': admin_username},
            {'label': 'Generated Card Ref', 'value': f"ID #{card_obj.id} (•••• {card_obj.last_four})" if card_obj else 'None'},
        ],
        'extra_note': "Card issuance audit recorded in regulatory docket.",
        'admin_url': f"{site_url}/admin/core/cardrequest/{card_request.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_withdrawal_decision_email(withdrawal, decision, admin_username='Admin'):
    """
    Dispatches determination notice when a Withdrawal Request is Approved/Disbursed or Rejected.
    decision: 'APPROVED' or 'REJECTED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = withdrawal.user
    applicant_name = user.get_full_name() or user.username
    is_approved = (decision == 'APPROVED')

    # 1. User Email
    if is_approved:
        user_subject = f"Withdrawal Clearance Approved & Disbursed: #{withdrawal.request_id}"
        status_label = "WITHDRAWAL APPROVED & DISBURSED"
        status_color = "success"
        heading = f"Withdrawal Approved & Disbursed (${withdrawal.amount:,.2f} USD)"
        message_body = (
            f"Your withdrawal clearance request (Ref: {withdrawal.request_id}) for the amount of "
            f"<strong>${withdrawal.amount:,.2f} USD</strong> via <strong>{withdrawal.payout_method}</strong> "
            f"has been formally <strong>APPROVED</strong> and submitted for disbursement."
        )
        extra_note = "Depending on your banking institution or payout provider, funds typically reflect within 1 to 3 business days."
    else:
        user_subject = f"Withdrawal Clearance Update: #{withdrawal.request_id}"
        status_label = "WITHDRAWAL REJECTED"
        status_color = "danger"
        heading = "Withdrawal Clearance Status Update"
        rejection_reason = withdrawal.admin_notes or "Minimum withdrawal threshold criteria or statutory clearance charges not met."
        message_body = (
            f"Your withdrawal clearance request (Ref: {withdrawal.request_id}) for ${withdrawal.amount:,.2f} USD "
            f"could not be approved at this time.<br><br>"
            f"<strong>Compliance Notice:</strong> <em>{rejection_reason}</em>"
        )
        extra_note = "Please ensure your account satisfies the minimum withdrawal requirement and that all clearance fees are settled."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Notice regarding your withdrawal request #{withdrawal.request_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': withdrawal.request_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': message_body,
        'details': [
            {'label': 'Request Reference', 'value': withdrawal.request_id},
            {'label': 'Amount', 'value': f"${withdrawal.amount:,.2f} USD"},
            {'label': 'Payout Method', 'value': withdrawal.payout_method},
            {'label': 'Decision', 'value': 'APPROVED' if is_approved else 'REJECTED'},
            {'label': 'Processed Date', 'value': event_date},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/accounts/withdraw/",
        'cta_text': "View Account Transactions",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] Withdrawal {decision}: #{withdrawal.request_id} (${withdrawal.amount:,.2f})"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"Withdrawal request #{withdrawal.request_id} marked as {decision}.",
        'status_label': f"WITHDRAWAL AUDIT: {decision}",
        'heading': f"Withdrawal Determination Executed: {decision}",
        'reference_id': withdrawal.request_id,
        'event_date': event_date,
        'message_body': (
            f"Withdrawal request <strong>#{withdrawal.request_id}</strong> for <strong>${withdrawal.amount:,.2f}</strong> "
            f"by user <strong>{user.username}</strong> has been marked as <strong>{decision}</strong> by {admin_username}."
        ),
        'details': [
            {'label': 'Request ID', 'value': withdrawal.request_id},
            {'label': 'User Username', 'value': user.username},
            {'label': 'User Email', 'value': user.email},
            {'label': 'Amount', 'value': f"${withdrawal.amount:,.2f} USD"},
            {'label': 'Payout Method', 'value': withdrawal.payout_method},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Admin Username', 'value': admin_username},
        ],
        'extra_note': "Audit log recorded in compliance archives.",
        'admin_url': f"{site_url}/admin/core/withdrawalrequest/{withdrawal.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_loan_decision_email(loan, decision, admin_username='Admin'):
    """
    Dispatches determination notice when a Loan Request is Approved or Rejected.
    decision: 'APPROVED' or 'REJECTED' or 'DISBURSED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = loan.user
    applicant_name = user.get_full_name() or user.username
    is_approved = (decision in ['APPROVED', 'DISBURSED'])

    # 1. User Email
    if is_approved:
        user_subject = f"Restitution Capital Advance Approved: #{loan.loan_id}"
        status_label = "LOAN ADVANCE APPROVED"
        status_color = "success"
        heading = f"Loan Application Approved (${loan.amount_requested:,.2f} USD)"
        message_body = (
            f"We are pleased to inform you that your Restitution Capital Advance application "
            f"(Ref: {loan.loan_id}) for <strong>${loan.amount_requested:,.2f} USD</strong> "
            f"has been <strong>APPROVED</strong> by the credit committee."
        )
        extra_note = "Your advance facility is scheduled for balance disbursement according to agreed terms."
    else:
        user_subject = f"Loan Application Determination Notice: #{loan.loan_id}"
        status_label = "LOAN APPLICATION DECLINED"
        status_color = "danger"
        heading = "Loan Application Review Update"
        rejection_reason = loan.admin_notes or "Credit underwriting criteria or collateral claim validation could not be satisfied."
        message_body = (
            f"Thank you for applying for a Restitution Capital Advance (Ref: {loan.loan_id}). "
            f"Following review by our credit underwriting desk, we regret to inform you that your application "
            f"could not be approved at this time.<br><br>"
            f"<strong>Determination Notice:</strong> <em>{rejection_reason}</em>"
        )
        extra_note = "You may re-apply after 30 days or once your primary restitution claim has progressed."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Notice regarding your loan application #{loan.loan_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': loan.loan_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': message_body,
        'details': [
            {'label': 'Loan Reference', 'value': loan.loan_id},
            {'label': 'Facility Purpose', 'value': loan.get_purpose_display()},
            {'label': 'Amount', 'value': f"${loan.amount_requested:,.2f} USD"},
            {'label': 'Term', 'value': f"{loan.term_months} Months"},
            {'label': 'APR', 'value': f"{loan.annual_interest_rate}%"},
            {'label': 'Determination', 'value': decision},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/accounts/loan/",
        'cta_text': "View Loan Details",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] Loan Application {decision}: #{loan.loan_id}"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"Loan {decision} for {user.username}.",
        'status_label': f"LOAN AUDIT: {decision}",
        'heading': f"Loan Application Determination: {decision}",
        'reference_id': loan.loan_id,
        'event_date': event_date,
        'message_body': (
            f"Loan application <strong>#{loan.loan_id}</strong> (${loan.amount_requested:,.2f}) for "
            f"<strong>{user.username}</strong> has been marked as <strong>{decision}</strong> by {admin_username}."
        ),
        'details': [
            {'label': 'Loan Docket', 'value': loan.loan_id},
            {'label': 'Applicant Username', 'value': user.username},
            {'label': 'Applicant Email', 'value': user.email},
            {'label': 'Amount', 'value': f"${loan.amount_requested:,.2f} USD"},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Admin Username', 'value': admin_username},
        ],
        'extra_note': "Audit log recorded in compliance archives.",
        'admin_url': f"{site_url}/admin/core/loanrequest/{loan.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_wire_decision_email(wire, decision, admin_username='Admin'):
    """
    Dispatches determination notice when an International Wire Transfer is Completed or Rejected.
    decision: 'COMPLETED' or 'REJECTED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = wire.user
    applicant_name = user.get_full_name() or user.username
    is_completed = (decision == 'COMPLETED')

    # 1. User Email
    if is_completed:
        user_subject = f"International Wire Disbursed & Completed: Ref #{wire.reference_id}"
        status_label = "WIRE COMPLETED & DISBURSED"
        status_color = "success"
        heading = f"Wire Transfer Disbursed ({wire.currency} {wire.amount:,.2f})"
        message_body = (
            f"Your international wire transfer (Ref: {wire.reference_id}) of "
            f"<strong>{wire.currency} {wire.amount:,.2f}</strong> to <strong>{wire.beneficiary_name}</strong> "
            f"has been successfully released and completed through our international correspondent banking network."
        )
        extra_note = "Funds are typically credited to the beneficiary institution within standard SWIFT value-dating (1 to 2 business days)."
    else:
        user_subject = f"International Wire Transfer Notice: Ref #{wire.reference_id}"
        status_label = "WIRE TRANSFER REJECTED"
        status_color = "danger"
        heading = "International Wire Transfer Update"
        rejection_reason = wire.admin_notes or "SWIFT routing validation error or AML compliance clearance could not be obtained."
        message_body = (
            f"Your international wire transfer instruction (Ref: {wire.reference_id}) for "
            f"{wire.currency} {wire.amount:,.2f} could not be completed.<br><br>"
            f"<strong>Compliance Notice:</strong> <em>{rejection_reason}</em>"
        )
        extra_note = "Please verify your recipient bank's SWIFT/BIC code and IBAN with your receiving bank."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Notice regarding your wire transfer #{wire.reference_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': wire.reference_id,
        'event_date': event_date,
        'recipient_name': applicant_name,
        'message_body': message_body,
        'details': [
            {'label': 'Wire Reference', 'value': wire.reference_id},
            {'label': 'Beneficiary Name', 'value': wire.beneficiary_name},
            {'label': 'Bank Name', 'value': wire.bank_name},
            {'label': 'SWIFT / BIC', 'value': wire.swift_bic},
            {'label': 'Amount', 'value': f"{wire.currency} {wire.amount:,.2f}"},
            {'label': 'Determination', 'value': 'COMPLETED' if is_completed else 'REJECTED'},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/accounts/international-wire/",
        'cta_text': "View International Wire Portal",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] Wire Transfer {decision}: #{wire.reference_id}"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"Wire transfer #{wire.reference_id} marked as {decision}.",
        'status_label': f"WIRE AUDIT: {decision}",
        'heading': f"International Wire Determination: {decision}",
        'reference_id': wire.reference_id,
        'event_date': event_date,
        'message_body': (
            f"International wire transfer <strong>#{wire.reference_id}</strong> ({wire.currency} {wire.amount:,.2f}) for "
            f"<strong>{user.username}</strong> has been marked as <strong>{decision}</strong> by {admin_username}."
        ),
        'details': [
            {'label': 'Wire Docket', 'value': wire.reference_id},
            {'label': 'Originating User', 'value': user.username},
            {'label': 'Beneficiary Name', 'value': wire.beneficiary_name},
            {'label': 'Amount', 'value': f"{wire.currency} {wire.amount:,.2f}"},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Admin Username', 'value': admin_username},
        ],
        'extra_note': "Audit log recorded in compliance archives.",
        'admin_url': f"{site_url}/admin/core/wiretransfer/{wire.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_claim_decision_email(claim, decision, admin_username='Case Specialist'):
    """
    Dispatches determination notice when a Claim is Approved, Completed, or Rejected.
    decision: 'APPROVED', 'COMPLETED', or 'REJECTED'
    """
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    is_positive = (decision in ['APPROVED', 'COMPLETED'])

    # 1. User Email
    if is_positive:
        user_subject = f"Restitution Claim {decision.capitalize()}: Docket #{claim.claim_id}"
        status_label = f"CLAIM {decision}"
        status_color = "success"
        heading = f"Restitution Authorized for Claim #{claim.claim_id}"
        message_body = (
            f"We are pleased to report a major milestone in your recovery file. "
            f"Your restitution claim against <strong>{claim.company_name}</strong> (Docket: {claim.claim_id}) "
            f"for the amount of <strong>${claim.amount_lost:,.2f} USD</strong> has reached <strong>{decision}</strong> status."
        )
        extra_note = "Your designated recovery specialist is coordinating restitution settlement. Please check your client dashboard."
    else:
        user_subject = f"Claim Review Update: Docket #{claim.claim_id}"
        status_label = "CLAIM CLOSED / REJECTED"
        status_color = "danger"
        heading = f"Determination Notice for Claim #{claim.claim_id}"
        rejection_reason = claim.agent_notes or "The evidence provided was insufficient to establish merchant liability under current banking chargeback rules."
        message_body = (
            f"Following thorough forensic investigation of your claim against {claim.company_name} (Docket: {claim.claim_id}), "
            f"our legal panel has concluded that this claim cannot be pursued further at this juncture.<br><br>"
            f"<strong>Forensic Report Summary:</strong> <em>{rejection_reason}</em>"
        )
        extra_note = "If you have new documentary evidence or supplementary proof to submit, you may request a case re-evaluation."

    user_context = {
        'email_subject': user_subject,
        'preheader': f"Notice regarding your claim #{claim.claim_id}.",
        'status_label': status_label,
        'status_color': status_color,
        'heading': heading,
        'reference_id': claim.claim_id,
        'event_date': event_date,
        'recipient_name': claim.full_name,
        'message_body': message_body,
        'details': [
            {'label': 'Claim Docket', 'value': claim.claim_id},
            {'label': 'Disputed Entity', 'value': claim.company_name},
            {'label': 'Amount in Dispute', 'value': f"${claim.amount_lost:,.2f} USD"},
            {'label': 'Determination', 'value': decision},
            {'label': 'Case Specialist', 'value': claim.assigned_agent or admin_username},
        ],
        'extra_note': extra_note,
        'cta_url': f"{site_url}/claim-status/",
        'cta_text': "View Claim Dossier",
    }
    send_html_email(
        subject=user_subject,
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[claim.email],
        is_admin=False
    )

    # 2. Admin Operational Audit Log Email
    admin_subject = f"[ADMIN AUDIT] Claim {decision}: #{claim.claim_id}"
    admin_context = {
        'email_subject': admin_subject,
        'preheader': f"Claim #{claim.claim_id} marked as {decision}.",
        'status_label': f"CLAIM AUDIT: {decision}",
        'heading': f"Claim Determination Executed: {decision}",
        'reference_id': claim.claim_id,
        'event_date': event_date,
        'message_body': (
            f"Claim <strong>#{claim.claim_id}</strong> (${claim.amount_lost:,.2f}) for "
            f"<strong>{claim.full_name}</strong> has been marked as <strong>{decision}</strong> by {admin_username}."
        ),
        'details': [
            {'label': 'Claim ID', 'value': claim.claim_id},
            {'label': 'Claimant Name', 'value': claim.full_name},
            {'label': 'Claimant Email', 'value': claim.email},
            {'label': 'Entity', 'value': claim.company_name},
            {'label': 'Amount', 'value': f"${claim.amount_lost:,.2f} USD"},
            {'label': 'Decision Recorded', 'value': decision},
            {'label': 'Admin Username', 'value': admin_username},
        ],
        'extra_note': "Audit log recorded in compliance archives.",
        'admin_url': f"{site_url}/admin/core/claim/{claim.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=admin_subject,
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )


def send_support_inquiry_emails(support_msg):
    """Dispatches separate emails when a client logs a support inquiry."""
    site_url = get_site_url()
    event_date = timezone.now().strftime('%B %d, %Y')
    user = support_msg.user_profile.user if support_msg.user_profile else None
    if not user:
        return
    client_name = user.get_full_name() or user.username

    # 1. User Email
    user_context = {
        'email_subject': f"Case Support Message Delivered: Ref #{user.profile.account_no}",
        'preheader': "Your communication has been routed to your assigned case specialist.",
        'status_label': 'MESSAGE DELIVERED',
        'status_color': 'info',
        'heading': "Support Communication Routed to Specialist",
        'reference_id': f"MSG-{support_msg.id:05d}",
        'event_date': event_date,
        'recipient_name': client_name,
        'message_body': (
            f"Your case communication has been delivered to your assigned Senior Forensic Case Specialist. "
            f"We will review your inquiry and respond directly via email or your client portal."
        ),
        'details': [
            {'label': 'Message Reference', 'value': f"MSG-{support_msg.id:05d}"},
            {'label': 'Client Account', 'value': user.profile.account_no},
            {'label': 'Dispatched At', 'value': event_date},
            {'label': 'Message Excerpt', 'value': support_msg.message[:120] + ('...' if len(support_msg.message) > 120 else '')},
        ],
        'extra_note': "For direct phone consultation with your case officer, you may call +1 (555) 123-4567 during standard hours.",
        'cta_url': f"{site_url}/accounts/support/",
        'cta_text': "View Case Support Portal",
    }
    send_html_email(
        subject=f"Case Support Message Delivered: Ref #{user.profile.account_no}",
        template_name="emails/user_notification.html",
        context=user_context,
        recipient_list=[user.email],
        is_admin=False
    )

    # 2. Admin Email
    admin_context = {
        'email_subject': f"[ADMIN CLIENT SUPPORT] New Message from {user.username} (Acc #{user.profile.account_no})",
        'preheader': f"Client support inquiry from {user.username}.",
        'status_label': 'CLIENT SUPPORT MESSAGE',
        'heading': f"New Case Inquiry: {user.username}",
        'reference_id': f"MSG-{support_msg.id:05d}",
        'event_date': event_date,
        'message_body': (
            f"Client <strong>{user.username}</strong> ({client_name}, Account: <code>{user.profile.account_no}</code>) "
            f"has sent a support message:"
        ),
        'details': [
            {'label': 'Message ID', 'value': f"MSG-{support_msg.id:05d}"},
            {'label': 'Client Username', 'value': user.username},
            {'label': 'Client Email', 'value': user.email},
            {'label': 'Client Phone', 'value': user.profile.phone or 'N/A'},
            {'label': 'Account Number', 'value': user.profile.account_no},
            {'label': 'Message Body', 'value': support_msg.message},
        ],
        'extra_note': "Respond directly through the user profile change form or via email.",
        'admin_url': f"{site_url}/admin/core/userprofile/{support_msg.user_profile.id}/change/",
    }
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', SUPPORT_EMAIL)
    send_html_email(
        subject=f"[ADMIN CLIENT SUPPORT] New Message from {user.username}",
        template_name="emails/admin_notification.html",
        context=admin_context,
        recipient_list=[admin_email],
        is_admin=True
    )

