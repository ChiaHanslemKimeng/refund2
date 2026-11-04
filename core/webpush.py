import json
import logging
from django.conf import settings
from django.utils import timezone
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

def send_web_push(title, body, url="/admin/"):
    """
    Sends native web push notifications to all registered admin/device subscriptions.
    Handles expired subscriptions (HTTP 404 or 410) by deleting them from the database.
    Payload includes title, body, url, icon, badge, sound, and vibration pattern mimicking WhatsApp.
    """
    from .models import PushSubscription

    subscriptions = PushSubscription.objects.all()
    if not subscriptions.exists():
        logger.info("No active web push subscriptions found.")
        return 0

    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
    vapid_admin_email = getattr(settings, 'VAPID_ADMIN_EMAIL', 'support@nexisrecovery.com')

    if not vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY not configured in settings.")
        return 0

    # Payload with high-priority WhatsApp-style options
    payload_dict = {
        "title": title,
        "body": body,
        "url": url,
        "icon": "/static/img/nexis_logo.svg",
        "badge": "/static/img/nexis_icon.svg",
        "vibrate": [200, 100, 200, 100, 200, 100, 200],
        "requireInteraction": True,
        "tag": f"nexis-admin-alert-{int(timezone.now().timestamp())}",
        "renotify": True,
        "silent": False,
        "data": {
            "url": url,
            "timestamp": int(timezone.now().timestamp() * 1000)
        }
    }
    payload_json = json.dumps(payload_dict)

    vapid_claims = {
        "sub": f"mailto:{vapid_admin_email}"
    }

    success_count = 0
    expired_ids = []

    for sub in subscriptions:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=payload_json,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
                ttl=86400
            )
            success_count += 1
        except WebPushException as ex:
            logger.warning(f"WebPush failed for subscription {sub.id}: {ex}")
            # Detect 404 or 410 (Unsubscribed or Gone)
            status_code = None
            if hasattr(ex, 'response') and ex.response is not None:
                status_code = getattr(ex.response, 'status_code', None)
            
            if status_code in [404, 410]:
                expired_ids.append(sub.id)
        except Exception as e:
            logger.error(f"Unexpected error sending web push to subscription {sub.id}: {e}")

    if expired_ids:
        PushSubscription.objects.filter(id__in=expired_ids).delete()
        logger.info(f"Cleaned up {len(expired_ids)} expired push subscription(s).")

    return success_count
