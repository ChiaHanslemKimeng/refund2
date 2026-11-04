# Nexis Cyber Recovery

A modern, institutional-grade Django web application for cyber asset tracking, digital forensics, and financial restitution.

## Design & Architecture
- **Theme**: Modern Dark Fintech & Cyber Recovery
- **Palette**: Deep Obsidian Canvas (`#070b14`), Glassmorphism Surface (`#0f172a`), Electric Cyan (`#00f2fe` / `#06b6d4`), Neon Emerald (`#10b981`), High-Contrast Typography (`Plus Jakarta Sans` & `JetBrains Mono`).
- **Features**:
  - **Public Forensic Portal**: Home, About, Services, Forensic Process, Verified Reviews, FAQs, Contact.
  - **Client Recovery Terminal**: Case submission, real-time cryptographic milestone tracking, in-app encrypted cards, KYC verification, transactions, and direct caseworker communications.
  - **Administrative Clearance Gateway**: Comprehensive Django Admin dashboard with VAPID web-push compliance alerts.
  - **Asset Localization**: Automated downloading of placeholder assets and vector branding.

## Setup Instructions

### 1. Activate Virtual Environment
- **Windows**:
  ```powershell
  .\venv\Scripts\activate
  ```
- **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations & Populate Data
```bash
python manage.py migrate
python manage.py populate_data
```

### 4. Run Server
```bash
python manage.py runserver 8001
```

## Default Sample Credentials
- **Superuser Admin**: `admin` / `Admin@Nexis2026!`
- **Sample Client**: `marcus_vance` / `Client@Nexis2026!`
- **Public Claim Tracking**: Claim ID `NX-784210` (Email: `marcus.vance@example.com`)
