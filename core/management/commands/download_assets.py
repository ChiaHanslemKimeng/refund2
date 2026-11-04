import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
from core.models import Testimonial, Partner

class Command(BaseCommand):
    help = 'Downloads static images and populates media files for the website'

    def handle(self, *args, **kwargs):
        # 1. Download Static Images
        static_img_dir = settings.BASE_DIR / 'static' / 'img'
        os.makedirs(static_img_dir, exist_ok=True)

        static_images = {
            'hero-bg.jpg': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&q=85&w=2000',
            'office-meeting.jpg': 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&q=85&w=2000',
            'about-team.jpg': 'https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&q=85&w=1600',
            'team-1.jpg': 'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&q=80&w=300',
            'team-2.jpg': 'https://images.unsplash.com/photo-1573496359-145752a95c93?auto=format&fit=crop&q=80&w=300',
            'team-3.jpg': 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&q=80&w=300',
            'team-4.jpg': 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&q=80&w=300',
        }

        self.stdout.write("Downloading static images...")
        for filename, url in static_images.items():
            filepath = static_img_dir / filename
            if not os.path.exists(filepath):
                try:
                    self.stdout.write(f"Downloading {filename}...")
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        self.stdout.write(self.style.SUCCESS(f"Saved {filename}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"Failed to download {filename}: Status {response.status_code}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error downloading {filename}: {e}"))
            else:
                self.stdout.write(f"{filename} already exists. Skipping.")

        # 2. Populate Testimonial Images
        self.stdout.write("Populating Testimonial images...")
        testimonials = Testimonial.objects.filter(image='')
        if testimonials.exists():
            for i, t in enumerate(testimonials):
                avatars = [
                    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200",
                    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200",
                    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200",
                    "https://images.unsplash.com/photo-1521119989659-a83eee488058?w=200",
                    "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200",
                    "https://images.unsplash.com/photo-1531427186611-ecfd6d936c79?w=200",
                    "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200",
                    "https://images.unsplash.com/photo-1554151228-14d9def656ec?w=200",
                    "https://images.unsplash.com/photo-1599566150163-29194dcaad36?w=200",
                    "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200",
                ]
                url = avatars[i % len(avatars)]
                
                try:
                    self.stdout.write(f"Downloading avatar for {t.name} from {url}...")
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        t.image.save(f"avatar_{t.id}.jpg", ContentFile(response.content), save=True)
                        self.stdout.write(self.style.SUCCESS(f"Updated {t.name}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error updating {t.name}: {e}"))
        else:
            self.stdout.write("All testimonials have images.")

        # 3. Populate Partner Logos (Using placeholders)
        self.stdout.write("Populating Partner logos...")
        partners = Partner.objects.filter(logo='')
        if partners.exists():
            for i, p in enumerate(partners):
                url = f"https://ui-avatars.com/api/?name={p.name}&background=random&color=fff&size=200"
                try:
                    self.stdout.write(f"Downloading logo for {p.name}...")
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        p.logo.save(f"logo_{p.id}.png", ContentFile(response.content), save=True)
                        self.stdout.write(self.style.SUCCESS(f"Updated {p.name}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error updating {p.name}: {e}"))
        else:
             self.stdout.write("All partners have logos.")

        self.stdout.write(self.style.SUCCESS("Asset download and population complete."))
