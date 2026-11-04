// Nexis Cyber Recovery - High Priority Web Push Service Worker (WhatsApp Style)

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
    let payload = {};
    if (event.data) {
        try {
            payload = event.data.json();
        } catch (e) {
            payload = {
                title: 'Nexis Administrative Alert',
                body: event.data.text()
            };
        }
    } else {
        payload = {
            title: 'Nexis Security Alert',
            body: 'A new case dossier or financial action requires clearance.'
        };
    }

    const title = payload.title || '🚨 Nexis Admin Alert';
    const targetUrl = (payload.data && payload.data.url) || payload.url || '/admin/';

    const options = {
        body: payload.body || 'New action requiring immediate administrative review.',
        icon: payload.icon || '/static/img/nexis_logo.svg',
        badge: payload.badge || '/static/img/nexis_icon.svg',
        // High priority vibration pattern: 200ms on, 100ms off, etc.
        vibrate: payload.vibrate || [200, 100, 200, 100, 200, 100, 200],
        requireInteraction: true,
        tag: payload.tag || ('nexis-alert-' + Date.now()),
        renotify: true,
        silent: false,
        data: {
            url: targetUrl,
            time: Date.now()
        },
        actions: [
            {
                action: 'open_review',
                title: 'Review Case'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/admin/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            // Check if there is already a window open with this URL
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.includes(targetUrl) && 'focus' in client) {
                    return client.focus();
                }
            }
            // If not open, open a new window
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
