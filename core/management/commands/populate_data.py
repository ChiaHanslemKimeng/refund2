from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from core.models import (
    UserProfile, Claim, Contact, InAppCreditCard, 
    SupportMessage
)

class Command(BaseCommand):
    help = 'Populates the database with realistic sample data for Nexis Cyber Recovery'

    def handle(self, *args, **kwargs):
        self.stdout.write('Populating Nexis Cyber Recovery database...')

        # 1. Create or update Admin User
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@nexisrecovery.com',
                'first_name': 'Nexis',
                'last_name': 'Forensics Admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('Admin@Nexis2026!')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created Superuser: admin (password: Admin@Nexis2026!)'))
        else:
            self.stdout.write('Superuser admin already exists.')

        # 2. Create Sample Client User
        client_user, created = User.objects.get_or_create(
            username='marcus_vance',
            defaults={
                'email': 'marcus.vance@example.com',
                'first_name': 'Marcus',
                'last_name': 'Vance',
                'is_active': True
            }
        )
        if created:
            client_user.set_password('Client@Nexis2026!')
            client_user.save()
            self.stdout.write(self.style.SUCCESS('Created Sample Client: marcus_vance (password: Client@Nexis2026!)'))
        
        # 3. Client UserProfile
        profile, p_created = UserProfile.objects.get_or_create(
            user=client_user,
            defaults={
                'account_no': '8492048192',
                'account_type': 'CHECKING',
                'balance': Decimal('48500.00'),
                'min_withdrawal_amount': Decimal('500.00'),
                'withdrawal_charge_amount': Decimal('0.00'),
                'is_withdrawal_charge_paid': True,
                'is_charge_paid': True,
                'charge_amount': Decimal('0.00'),
                'is_kyc_verified': True,
                'country': 'United States',
                'phone': '+1 (555) 382-9014'
            }
        )
        if p_created:
            self.stdout.write(self.style.SUCCESS(f'Created UserProfile for {client_user.username} with balance ${profile.balance}'))

        # 4. Sample Claim
        claim, c_created = Claim.objects.get_or_create(
            claim_id='NX-784210',
            defaults={
                'full_name': 'Marcus Vance',
                'email': 'marcus.vance@example.com',
                'phone': '+1 (555) 382-9014',
                'country': 'United States',
                'refund_type': 'CRYPTO_SCAM',
                'amount_lost': Decimal('94000.00'),
                'transaction_date': timezone.now().date(),
                'company_name': 'NovaTrade Offshore FX & Liquidity Broker',
                'description': 'Offshore trading platform blocked capital withdrawal and fabricated fake margin tax demands. Blockchain address clustering traced funds through 2 mixers into a centralized deposit wallet.',
                'status': 'IN_PROGRESS',
                'assigned_agent': 'Agent V. Sterling (Lead Cyber Forensics)',
                'agent_notes': 'Forensic trace complete. Destination exchange compliance desk notified under emergency AML freeze protocol.',
                'preferred_contact': 'EMAIL'
            }
        )
        if c_created:
            self.stdout.write(self.style.SUCCESS(f'Created Sample Claim: {claim.claim_id}'))

        # 5. Sample Virtual Card
        card, card_created = InAppCreditCard.objects.get_or_create(
            user=client_user,
            card_number='4532890124987612',
            defaults={
                'cardholder_name': 'MARCUS VANCE',
                'card_type': 'VISA',
                'card_source': 'IN_APP',
                'exp_month': '08',
                'exp_year': '29',
                'cvv': '482',
                'billing_zip': '10005',
                'is_primary': True
            }
        )
        if card_created:
            self.stdout.write(self.style.SUCCESS('Created Sample In-App Settlement Card'))

        # 6. Sample Support Message
        msg, msg_created = SupportMessage.objects.get_or_create(
            user_profile=profile,
            message='Forensic trace report successfully generated for case NX-784210. Destination exchange confirmed compliance hold.',
            defaults={
                'is_from_admin': True,
                'is_read': False
            }
        )
        if msg_created:
            self.stdout.write(self.style.SUCCESS('Created Support Message'))

        # 7. Sample Inquiries
        contact, contact_created = Contact.objects.get_or_create(
            email='david.lindqvist@example.com',
            defaults={
                'name': 'David Lindqvist',
                'phone': '+46 8 123 4567',
                'subject': 'DeFi Smart Contract Exploit Restitution',
                'message': 'Our liquidity pool was drained by an unauthorized flash loan attack. Can your forensics team trace the recipient addresses?'
            }
        )
        if contact_created:
            self.stdout.write(self.style.SUCCESS('Created Sample Contact Inquiry'))

        self.stdout.write(self.style.SUCCESS('\n--- NEXIS CYBER RECOVERY DATABASE POPULATED SUCCESSFULLY ---'))
        self.stdout.write(f'Admin Login: admin / Admin@Nexis2026!')
        self.stdout.write(f'Client Login: marcus_vance / Client@Nexis2026!')
        self.stdout.write(f'Claim ID for Public Tracking: NX-784210 (email: marcus.vance@example.com)')
