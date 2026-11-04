from django.conf import settings

def vapid_settings(request):
    return {
        'VAPID_PUBLIC_KEY': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        'VAPID_ADMIN_EMAIL': getattr(settings, 'VAPID_ADMIN_EMAIL', ''),
    }
