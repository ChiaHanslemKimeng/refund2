from django.urls import path
from .views import (
    HomeView, AboutView, ServicesView, HowItWorksView, 
    ReviewsView, TestimonialsView, FAQView, ContactView, 
    SubmitClaimView, ClaimSuccessView, CheckStatusView,
    RegisterView, UserLoginView, UserLogoutView,
    DashboardView, ReceiveMoneyView, PayChargeView,
    TransactionsView, MyCardsView, RequestCardView, DeleteCardView, SettingsView,
    UserPasswordChangeView, DeactivateAccountView, SupportView,
    AdminUserChatView, GetNewMessagesView, KYCVerificationView, LocalTransferView,
    DepositView, WithdrawView, InternationalWireView, LoanRequestView,
    save_push_subscription, test_send_push_notification,
    service_worker_view, manifest_view
)
from django.views.generic import TemplateView

urlpatterns = [
    # Public Pages
    path('', HomeView.as_view(), name='home'),
    path('about/', AboutView.as_view(), name='about'),
    path('services/', ServicesView.as_view(), name='services'),
    path('how-it-works/', HowItWorksView.as_view(), name='how_it_works'),
    path('reviews/', ReviewsView.as_view(), name='reviews'),
    path('testimonials/', TestimonialsView.as_view(), name='testimonials'),
    path('faq/', FAQView.as_view(), name='faq'),
    path('contact/', ContactView.as_view(), name='contact'),

    # Legal Pages
    path('privacy-policy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('terms-conditions/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('disclaimer/', TemplateView.as_view(template_name='legal/disclaimer.html'), name='disclaimer'),

    # Accounts
    path('accounts/register/', RegisterView.as_view(), name='register'),
    path('accounts/login/', UserLoginView.as_view(), name='login'),
    path('accounts/logout/', UserLogoutView.as_view(), name='logout'),
    path('accounts/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('accounts/deposit/', DepositView.as_view(), name='deposit'),
    path('accounts/withdraw/', WithdrawView.as_view(), name='withdraw'),
    path('accounts/loans/', LoanRequestView.as_view(), name='loan_request'),
    path('accounts/kyc/', KYCVerificationView.as_view(), name='kyc_verification'),
    path('accounts/transfers/local/', LocalTransferView.as_view(), name='local_transfer'),
    path('accounts/transfers/wire/', InternationalWireView.as_view(), name='international_wire'),
    path('accounts/transactions/', TransactionsView.as_view(), name='transactions'),
    path('accounts/my-cards/', MyCardsView.as_view(), name='my_cards'),
    path('accounts/my-cards/request/', RequestCardView.as_view(), name='request_card'),
    path('accounts/my-cards/delete/<int:card_id>/', DeleteCardView.as_view(), name='delete_card'),
    path('accounts/settings/', SettingsView.as_view(), name='settings'),
    path('accounts/change-password/', UserPasswordChangeView.as_view(), name='change_password'),
    path('accounts/deactivate/', DeactivateAccountView.as_view(), name='deactivate_account'),
    path('accounts/receive-money/', ReceiveMoneyView.as_view(), name='receive_money'),
    path('accounts/pay-charge/', PayChargeView.as_view(), name='pay_charge'),
    path('accounts/support/', SupportView.as_view(), name='support'),
    path('admin/chat/<int:profile_id>/', AdminUserChatView.as_view(), name='admin_user_chat'),
    path('api/messages/<int:profile_id>/', GetNewMessagesView.as_view(), name='get_new_messages'),

    # Client Portal
    path('portal/submit/', SubmitClaimView.as_view(), name='submit_claim'),
    path('portal/success/<str:claim_id>/', ClaimSuccessView.as_view(), name='claim_success'),
    path('portal/status/', CheckStatusView.as_view(), name='check_status'),

    # PWA & Web Push Endpoints
    path('sw.js', service_worker_view, name='service_worker'),
    path('manifest.json', manifest_view, name='pwa_manifest'),
    path('api/push/subscribe/', save_push_subscription, name='save_push_subscription'),
    path('api/push/test/', test_send_push_notification, name='test_push_notification'),
]

