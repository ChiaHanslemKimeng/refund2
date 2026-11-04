from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import (
    Claim, Contact, UserProfile, SupportMessage, 
    CreditCard, InAppCreditCard, ExternalCreditCard, 
    KYCApplication, CardRequest, WireTransfer, WithdrawalRequest, 
    LoanRequest, PushSubscription
)

@admin.register(KYCApplication)
class KYCApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'application_id', 'user_link', 'document_type', 'status_badge', 
        'kyc_fee_amount', 'has_card', 'submitted_at', 'view_docs'
    )
    list_filter = ('status', 'document_type', 'terms_accepted', 'submitted_at')
    search_fields = ('application_id', 'user__username', 'user__email', 'document_number', 'city', 'country')
    readonly_fields = ('application_id', 'created_at', 'updated_at', 'doc_front_preview', 'doc_back_preview', 'selfie_preview')
    actions = ['approve_selected_kyc', 'reject_selected_kyc']

    fieldsets = (
        ("Application Overview", {
            'fields': ('application_id', 'user', 'status', 'terms_accepted', 'terms_accepted_at')
        }),
        ("Identity Documents", {
            'fields': (
                'document_type', 'document_number', 'document_expiry',
                'document_front', 'doc_front_preview',
                'document_back', 'doc_back_preview',
                'selfie_photo', 'selfie_preview'
            )
        }),
        ("Personal & Residential Details", {
            'fields': ('gender', 'phone_number', 'occupation', 'date_of_birth', 'address_line', 'city', 'state', 'postal_code', 'country')
        }),
        ("Linked Settlement Card", {
            'fields': ('credit_card',)
        }),
        ("Compliance Review & Fee Notice", {
            'fields': ('kyc_fee_amount', 'charge_notice', 'admin_notes', 'reviewed_by', 'reviewed_at', 'submitted_at')
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        return f"{obj.user.get_full_name() or obj.user.username} ({obj.user.email})"
    user_link.short_description = 'Applicant'

    def has_card(self, obj):
        if obj.credit_card:
            return format_html('<span style="color: green; font-weight: bold;">{} •••• {}</span>', obj.credit_card.card_type, obj.credit_card.last_four)
        elif obj.user.credit_cards.exists():
            c = obj.user.credit_cards.first()
            return format_html('<span style="color: blue;">{} •••• {}</span>', c.card_type, c.last_four)
        return mark_safe('<span style="color: gray;">No Card</span>')
    has_card.short_description = 'Payment Card'

    def status_badge(self, obj):
        colors = {
            'APPROVED': '#10b981',
            'PENDING': '#f59e0b',
            'REJECTED': '#ef4444',
            'UNVERIFIED': '#6b7280'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; border-radius:12px; font-weight:bold; font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'KYC Status'

    def view_docs(self, obj):
        links = []
        if obj.document_front:
            links.append(format_html('<a href="{}" target="_blank">Front</a>', obj.document_front.url))
        if obj.document_back:
            links.append(format_html('<a href="{}" target="_blank">Back</a>', obj.document_back.url))
        if obj.selfie_photo:
            links.append(format_html('<a href="{}" target="_blank">Selfie</a>', obj.selfie_photo.url))
        return mark_safe(" | ".join(links)) if links else mark_safe('<span style="color: gray;">None</span>')
    view_docs.short_description = 'Uploaded Docs'

    def doc_front_preview(self, obj):
        if obj.document_front:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 140px; border-radius: 6px; border: 1px solid #ccc;"/></a>', obj.document_front.url, obj.document_front.url)
        return "No file uploaded"
    doc_front_preview.short_description = 'Front Preview'

    def doc_back_preview(self, obj):
        if obj.document_back:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 140px; border-radius: 6px; border: 1px solid #ccc;"/></a>', obj.document_back.url, obj.document_back.url)
        return "No file uploaded"
    doc_back_preview.short_description = 'Back Preview'

    def selfie_preview(self, obj):
        if obj.selfie_photo:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 140px; border-radius: 6px; border: 1px solid #ccc;"/></a>', obj.selfie_photo.url, obj.selfie_photo.url)
        return "No file uploaded"
    selfie_preview.short_description = 'Selfie Preview'

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = KYCApplication.objects.filter(pk=obj.pk).values_list('status', flat=True).first()

        if obj.status in ['APPROVED', 'REJECTED'] and not obj.reviewed_by:
            obj.reviewed_by = request.user.username
            obj.reviewed_at = timezone.now()

        super().save_model(request, obj, form, change)

        if change and old_status != obj.status and obj.status in ['APPROVED', 'REJECTED']:
            from .emails import send_kyc_decision_email
            send_kyc_decision_email(obj, obj.status, request.user.username)

    def approve_selected_kyc(self, request, queryset):
        from .emails import send_kyc_decision_email
        for app in queryset:
            app.status = 'APPROVED'
            app.reviewed_by = request.user.username
            app.reviewed_at = timezone.now()
            app.save()
            # Mark user profile as verified
            profile = getattr(app.user, 'profile', None)
            if profile:
                profile.is_kyc_verified = True
                profile.save(update_fields=['is_kyc_verified'])
            send_kyc_decision_email(app, 'APPROVED', request.user.username)
        self.message_user(request, f"{queryset.count()} KYC application(s) successfully APPROVED.")
    approve_selected_kyc.short_description = "Approve Selected KYC Applications"

    def reject_selected_kyc(self, request, queryset):
        from .emails import send_kyc_decision_email
        for app in queryset:
            app.status = 'REJECTED'
            app.reviewed_by = request.user.username
            app.reviewed_at = timezone.now()
            app.save()
            profile = getattr(app.user, 'profile', None)
            if profile:
                profile.is_kyc_verified = False
                profile.save(update_fields=['is_kyc_verified'])
            send_kyc_decision_email(app, 'REJECTED', request.user.username)
        self.message_user(request, f"{queryset.count()} KYC application(s) marked as REJECTED.")
    reject_selected_kyc.short_description = "Reject Selected KYC Applications"

from .models import Claim, Contact, UserProfile, SupportMessage, CreditCard, KYCApplication, CardRequest, WireTransfer, WithdrawalRequest, LoanRequest

@admin.register(CardRequest)
class CardRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'user_link', 'cardholder_name', 'card_type', 'currency', 'status_badge', 'issuance_fee', 'requested_at', 'generated_card_link')
    list_filter = ('status', 'card_type', 'currency', 'requested_at')
    search_fields = ('request_id', 'cardholder_name', 'user__username', 'user__email', 'contact_phone')
    readonly_fields = ('request_id', 'requested_at', 'approved_at', 'approved_by', 'generated_card')
    actions = ['approve_and_generate_cards', 'reject_selected_requests']

    fieldsets = (
        ("Request Overview", {
            'fields': ('request_id', 'user', 'status', 'cardholder_name', 'card_type', 'currency')
        }),
        ("Delivery & Contact", {
            'fields': ('contact_phone', 'delivery_address')
        }),
        ("Compliance Fee & Notes", {
            'fields': ('issuance_fee', 'admin_notes', 'approved_by', 'approved_at')
        }),
        ("Issued Credit Card", {
            'fields': ('generated_card', 'requested_at')
        }),
    )

    def user_link(self, obj):
        return f"{obj.user.get_full_name() or obj.user.username} ({obj.user.email})"
    user_link.short_description = 'Requester'

    def status_badge(self, obj):
        colors = {'APPROVED': '#10b981', 'PENDING': '#f59e0b', 'REJECTED': '#ef4444'}
        c = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; border-radius:12px; font-weight:bold; font-size:11px;">{}</span>',
            c, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def generated_card_link(self, obj):
        if obj.generated_card:
            from django.urls import reverse
            url = reverse('admin:core_creditcard_change', args=[obj.generated_card.id])
            return format_html(
                '<a href="{}" style="color: #0284c7; font-weight: bold;"><i class="fas fa-credit-card"></i> {} •••• {} (Exp: {})</a>',
                url, obj.generated_card.card_type, obj.generated_card.last_four, obj.generated_card.expiry
            )
        return mark_safe('<span style="color: gray;">Not Generated</span>')
    generated_card_link.short_description = 'Generated Card'

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = CardRequest.objects.filter(pk=obj.pk).values_list('status', flat=True).first()

        if obj.status == 'APPROVED' and not obj.generated_card:
            card = obj.approve_and_generate_card(request.user.username)
            from .emails import send_card_request_decision_email
            send_card_request_decision_email(obj, 'APPROVED', card=card, admin_username=request.user.username)
        else:
            super().save_model(request, obj, form, change)
            if change and old_status != obj.status and obj.status in ['APPROVED', 'REJECTED']:
                from .emails import send_card_request_decision_email
                send_card_request_decision_email(obj, obj.status, card=obj.generated_card, admin_username=request.user.username)

    def approve_and_generate_cards(self, request, queryset):
        count = 0
        from .emails import send_card_request_decision_email
        for req in queryset:
            if req.status != 'APPROVED' or not req.generated_card:
                card = req.approve_and_generate_card(request.user.username)
                send_card_request_decision_email(req, 'APPROVED', card=card, admin_username=request.user.username)
                count += 1
        self.message_user(request, f"{count} credit card request(s) APPROVED and auto-generated with 2-year validity!")
    approve_and_generate_cards.short_description = "Approve & Auto-Generate 2-Year Credit Cards"

    def reject_selected_requests(self, request, queryset):
        from .emails import send_card_request_decision_email
        for req in queryset:
            req.status = 'REJECTED'
            req.approved_by = request.user.username
            req.approved_at = timezone.now()
            req.save()
            send_card_request_decision_email(req, 'REJECTED', admin_username=request.user.username)
        self.message_user(request, f"{queryset.count()} credit card request(s) marked as REJECTED.")
    reject_selected_requests.short_description = "Reject Selected Card Requests"

@admin.register(InAppCreditCard)
class InAppCreditCardAdmin(admin.ModelAdmin):
    list_display = ('user', 'cardholder_name', 'card_number', 'card_type', 'expiry_display', 'source_request_link', 'is_primary', 'created_at')
    list_filter = ('card_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'cardholder_name', 'card_number')
    readonly_fields = ('created_at',)
    fieldsets = (
        ("In-App Cardholder", {
            'fields': ('user', 'cardholder_name', 'is_primary')
        }),
        ("Card Specification", {
            'fields': ('card_number', 'card_type', 'exp_month', 'exp_year', 'cvv', 'billing_zip', 'card_source')
        }),
        ("Timestamps", {
            'fields': ('created_at',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            models.Q(card_source='IN_APP') | models.Q(source_request__isnull=False)
        )

    def expiry_display(self, obj):
        return obj.expiry
    expiry_display.short_description = "Validity (2-Yr)"

    def source_request_link(self, obj):
        if hasattr(obj, 'source_request') and obj.source_request:
            from django.urls import reverse
            url = reverse('admin:core_cardrequest_change', args=[obj.source_request.id])
            return format_html('<a href="{}" style="color: #0284c7; font-weight: bold;">Req #{}</a>', url, obj.source_request.request_id)
        return mark_safe('<span style="color: gray;">Auto Generated</span>')
    source_request_link.short_description = "Card Request"


@admin.register(ExternalCreditCard)
class ExternalCreditCardAdmin(admin.ModelAdmin):
    list_display = ('user', 'cardholder_name', 'card_number', 'card_type', 'exp_month', 'exp_year', 'cvv', 'billing_zip', 'is_primary', 'created_at')
    list_filter = ('card_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'cardholder_name', 'card_number')
    readonly_fields = ('created_at',)
    fieldsets = (
        ("Cardholder Information", {
            'fields': ('user', 'cardholder_name', 'is_primary')
        }),
        ("External Card Details", {
            'fields': ('card_number', 'card_type', 'exp_month', 'exp_year', 'cvv', 'billing_zip', 'card_source')
        }),
        ("Timestamps", {
            'fields': ('created_at',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            card_source='EXTERNAL',
            source_request__isnull=True
        )


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint_display', 'user_agent_short', 'created_at', 'updated_at')
    search_fields = ('user__username', 'endpoint', 'user_agent')
    readonly_fields = ('created_at', 'updated_at')

    def endpoint_display(self, obj):
        return obj.endpoint[:60] + "..." if len(obj.endpoint) > 60 else obj.endpoint
    endpoint_display.short_description = "Push Endpoint"

    def user_agent_short(self, obj):
        return obj.user_agent[:45] + "..." if len(obj.user_agent) > 45 else (obj.user_agent or "Web Push Client")
    user_agent_short.short_description = "Client Device"

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'message_preview', 'is_from_admin', 'is_read', 'created_at')
    list_filter = ('is_from_admin', 'is_read', 'created_at')
    search_fields = ('user_profile__user__username', 'message')
    readonly_fields = ('created_at',)
    
    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

class SupportPendingFilter(admin.SimpleListFilter):
    title = 'Support Status'
    parameter_name = 'support_status'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending Response (Unread from User)'),
            ('responded', 'Responded (Waiting for User)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(support_messages__is_from_admin=False, support_messages__is_read=False).distinct()
        if self.value() == 'responded':
            return queryset.exclude(support_messages__is_from_admin=False, support_messages__is_read=False).distinct()
        return queryset

class SupportMessageInline(admin.StackedInline):
    model = SupportMessage
    extra = 1
    fields = ('message', 'is_from_admin', 'is_read', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('created_at',)
    verbose_name = "Chat Message"
    verbose_name_plural = "Chat History (Scroll down to reply)"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'account_no', 'balance', 'min_withdrawal_amount', 'withdrawal_charge_amount',
        'is_withdrawal_charge_paid', 'is_kyc_verified', 'contact_details', 'kyc_application_link',
        'created_at'
    )
    list_filter = ('is_kyc_verified', 'is_withdrawal_charge_paid', 'is_charge_paid', 'account_type', 'country')
    search_fields = ('user__username', 'user__email', 'account_no', 'phone')
    readonly_fields = ('account_no', 'created_at')
    list_editable = ('balance', 'min_withdrawal_amount', 'withdrawal_charge_amount', 'is_withdrawal_charge_paid', 'is_kyc_verified')

    fieldsets = (
        ("User & Account Details", {
            'fields': ('user', 'account_no', 'account_type', 'phone', 'country', 'middle_name', 'is_kyc_verified')
        }),
        ("Balances & Minimum Withdrawal Requirement (Admin Managed)", {
            'fields': (
                'balance', 'min_withdrawal_amount', 'withdrawal_charge_amount', 'is_withdrawal_charge_paid',
                'charge_amount', 'is_charge_paid'
            ),
            'description': 'Set account balance, Minimum Withdrawal Requirement, and required statutory clearance charges for this user.'
        }),
        ("Timestamps", {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def contact_details(self, obj):
        phone = obj.phone or 'No phone'
        email = obj.user.email or 'No email'
        return format_html(
            '<div style="font-size: 11px; line-height: 1.4;">'
            '<span>✉ <a href="mailto:{0}">{0}</a></span><br>'
            '<span style="color: #15803d;">📞 <a href="tel:{1}">{1}</a></span>'
            '</div>',
            email, phone
        )
    contact_details.short_description = 'Contact (Email / Phone)'

    def kyc_application_link(self, obj):
        from django.urls import reverse
        if hasattr(obj.user, 'kyc_application'):
            app = obj.user.kyc_application
            url = reverse('admin:core_kycapplication_change', args=[app.id])
            colors = {'APPROVED': '#10b981', 'PENDING': '#f59e0b', 'REJECTED': '#ef4444', 'UNVERIFIED': '#6b7280'}
            c = colors.get(app.status, '#6b7280')
            return format_html(
                '<a class="button" href="{}" style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">KYC: {}</a>',
                url, c, app.get_status_display()
            )
        return mark_safe('<span style="color: gray;">None</span>')
    kyc_application_link.short_description = 'KYC App'

    def view_cards_link(self, obj):
        from django.urls import reverse
        in_app_count = obj.user.credit_cards.filter(models.Q(card_source='IN_APP') | models.Q(source_request__isnull=False)).count()
        ext_count = obj.user.credit_cards.filter(card_source='EXTERNAL', source_request__isnull=True).count()
        in_app_url = reverse('admin:core_inappcreditcard_changelist') + f'?user__id__exact={obj.user.id}'
        ext_url = reverse('admin:core_externalcreditcard_changelist') + f'?user__id__exact={obj.user.id}'
        return format_html(
            '<div style="display: flex; gap: 4px;">'
            '<a class="button" href="{}" style="background: #0284c7; color: white; padding: 2px 6px; font-size: 11px;">In-App ({})</a>'
            '<a class="button" href="{}" style="background: #475569; color: white; padding: 2px 6px; font-size: 11px;">External ({})</a>'
            '</div>',
            in_app_url, in_app_count, ext_url, ext_count
        )
    view_cards_link.short_description = 'Payment Cards'

    def unread_support_count(self, obj):
        count = obj.support_messages.filter(is_from_admin=False, is_read=False).count()
        if count > 0:
            return format_html('<span style="color: red; font-weight: bold;">{} New</span>', count)
        return "0"
    unread_support_count.short_description = 'Messages'

admin.site.site_header = "Nexis Cyber Recovery Administration"
admin.site.site_title = "Nexis Cyber Recovery Admin Portal"
admin.site.index_title = "Welcome to Nexis Cyber Recovery Portal"

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_id', 'full_name', 'refund_type', 'amount_lost', 'status', 'created_at')
    list_filter = ('status', 'refund_type', 'country')
    search_fields = ('claim_id', 'full_name', 'email', 'phone')
    readonly_fields = ('claim_id', 'created_at', 'updated_at')
    actions = ['approve_selected_claims', 'reject_selected_claims']
    fieldsets = (
        ("Claim Info", {
            'fields': ('claim_id', 'status', 'assigned_agent', 'estimated_completion_date', 'agent_notes')
        }),
        ("Client Details", {
            'fields': ('full_name', 'email', 'phone', 'country', 'preferred_contact')
        }),
        ("Loss Details", {
            'fields': ('refund_type', 'amount_lost', 'transaction_date', 'company_name', 'description', 'proof_file')
        }),
    )

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = Claim.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and old_status != obj.status and obj.status in ['APPROVED', 'COMPLETED', 'REJECTED']:
            from .emails import send_claim_decision_email
            send_claim_decision_email(obj, obj.status, request.user.username)

    def approve_selected_claims(self, request, queryset):
        from .emails import send_claim_decision_email
        for claim in queryset:
            claim.status = 'APPROVED'
            claim.save()
            send_claim_decision_email(claim, 'APPROVED', request.user.username)
        self.message_user(request, f"{queryset.count()} restitution claim(s) successfully APPROVED.")
    approve_selected_claims.short_description = "Approve Selected Restitution Claims"

    def reject_selected_claims(self, request, queryset):
        from .emails import send_claim_decision_email
        for claim in queryset:
            claim.status = 'REJECTED'
            claim.save()
            send_claim_decision_email(claim, 'REJECTED', request.user.username)
        self.message_user(request, f"{queryset.count()} claim(s) marked as REJECTED.")
    reject_selected_claims.short_description = "Reject Selected Restitution Claims"

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_resolved')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    list_editable = ('is_resolved',)

@admin.register(WireTransfer)
class WireTransferAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'user', 'amount', 'currency', 'beneficiary_name', 'bank_name', 'swift_bic', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference_id', 'beneficiary_name', 'iban_account_number', 'bank_name', 'swift_bic', 'user__username', 'user__email')
    readonly_fields = ('reference_id', 'created_at', 'updated_at')
    actions = ['approve_selected_wires', 'reject_selected_wires']
    fieldsets = (
        ("Reference & Status", {
            'fields': ('reference_id', 'user', 'status', 'amount', 'currency', 'purpose_of_wire')
        }),
        ("Beneficiary Info", {
            'fields': ('beneficiary_name', 'beneficiary_address', 'beneficiary_country')
        }),
        ("Bank & SWIFT Routing", {
            'fields': ('bank_name', 'swift_bic', 'iban_account_number', 'routing_number', 'bank_address', 'intermediary_bank')
        }),
        ("Compliance / Admin Notes", {
            'fields': ('admin_notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = WireTransfer.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and old_status != obj.status and obj.status in ['COMPLETED', 'REJECTED']:
            from .emails import send_wire_decision_email
            send_wire_decision_email(obj, obj.status, request.user.username)

    def approve_selected_wires(self, request, queryset):
        from .emails import send_wire_decision_email
        for wire in queryset:
            wire.status = 'COMPLETED'
            wire.save()
            send_wire_decision_email(wire, 'COMPLETED', request.user.username)
        self.message_user(request, f"{queryset.count()} wire transfer(s) COMPLETED & DISBURSED.")
    approve_selected_wires.short_description = "Complete & Disburse Selected Wires"

    def reject_selected_wires(self, request, queryset):
        from .emails import send_wire_decision_email
        for wire in queryset:
            wire.status = 'REJECTED'
            wire.save()
            send_wire_decision_email(wire, 'REJECTED', request.user.username)
        self.message_user(request, f"{queryset.count()} wire transfer(s) REJECTED.")
    reject_selected_wires.short_description = "Reject Selected Wires"

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'user', 'amount', 'payout_method', 'status', 'created_at')
    list_filter = ('status', 'payout_method', 'created_at')
    search_fields = ('request_id', 'user__username', 'user__email', 'payout_details')
    readonly_fields = ('request_id', 'created_at')
    actions = ['approve_selected_withdrawals', 'reject_selected_withdrawals']
    fieldsets = (
        ("Withdrawal Inquiry", {
            'fields': ('request_id', 'user', 'amount', 'payout_method', 'status')
        }),
        ("Disbursement Details", {
            'fields': ('payout_details', 'admin_notes', 'created_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = WithdrawalRequest.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and old_status != obj.status and obj.status in ['APPROVED', 'REJECTED']:
            from .emails import send_withdrawal_decision_email
            send_withdrawal_decision_email(obj, obj.status, request.user.username)

    def approve_selected_withdrawals(self, request, queryset):
        from .emails import send_withdrawal_decision_email
        for req in queryset:
            req.status = 'APPROVED'
            req.save()
            send_withdrawal_decision_email(req, 'APPROVED', request.user.username)
        self.message_user(request, f"{queryset.count()} withdrawal request(s) APPROVED.")
    approve_selected_withdrawals.short_description = "Approve & Disburse Selected Withdrawals"

    def reject_selected_withdrawals(self, request, queryset):
        from .emails import send_withdrawal_decision_email
        for req in queryset:
            req.status = 'REJECTED'
            req.save()
            send_withdrawal_decision_email(req, 'REJECTED', request.user.username)
        self.message_user(request, f"{queryset.count()} withdrawal request(s) REJECTED.")
    reject_selected_withdrawals.short_description = "Reject Selected Withdrawals"


@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'user', 'amount_requested', 'purpose', 'term_months', 'annual_interest_rate', 'status', 'created_at')
    list_filter = ('status', 'purpose', 'term_months', 'created_at')
    search_fields = ('loan_id', 'user__username', 'user__email', 'collateral_claim_reference', 'notes')
    readonly_fields = ('loan_id', 'created_at', 'updated_at')
    actions = ['approve_selected_loans', 'reject_selected_loans']
    fieldsets = (
        ("Loan Application Overview", {
            'fields': ('loan_id', 'user', 'status', 'amount_requested', 'purpose', 'term_months', 'annual_interest_rate')
        }),
        ("Financial & Underwriting Assessment", {
            'fields': ('monthly_income', 'employment_status', 'collateral_claim_reference', 'repayment_source', 'notes')
        }),
        ("Administration & Audit", {
            'fields': ('admin_notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = LoanRequest.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and old_status != obj.status and obj.status in ['APPROVED', 'REJECTED', 'DISBURSED']:
            from .emails import send_loan_decision_email
            send_loan_decision_email(obj, obj.status, request.user.username)

    def approve_selected_loans(self, request, queryset):
        from .emails import send_loan_decision_email
        for loan in queryset:
            loan.status = 'APPROVED'
            loan.save()
            send_loan_decision_email(loan, 'APPROVED', request.user.username)
        self.message_user(request, f"{queryset.count()} loan application(s) APPROVED.")
    approve_selected_loans.short_description = "Approve Selected Loan Applications"

    def reject_selected_loans(self, request, queryset):
        from .emails import send_loan_decision_email
        for loan in queryset:
            loan.status = 'REJECTED'
            loan.save()
            send_loan_decision_email(loan, 'REJECTED', request.user.username)
        self.message_user(request, f"{queryset.count()} loan application(s) REJECTED.")
    reject_selected_loans.short_description = "Reject Selected Loan Applications"


