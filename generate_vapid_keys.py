import os
import base64
from pathlib import Path
from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization

def generate_keys():
    v = Vapid()
    v.generate_keys()
    
    base_dir = Path(__file__).resolve().parent
    pem_path = base_dir / 'vapid_private.pem'
    v.save_key(str(pem_path))
    
    pub_bytes = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint
    )
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')
    
    print("\n================ VAPID KEYS GENERATED ================")
    print(f"Private Key saved to: {pem_path}")
    print("\nAdd the following lines to your .env file:\n")
    print(f"VAPID_PUBLIC_KEY={pub_b64}")
    print(f"VAPID_PRIVATE_KEY={pem_path}")
    print("VAPID_ADMIN_EMAIL=support@nexisrecovery.com")
    print("======================================================\n")

    env_file = base_dir / '.env'
    lines = []
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = [l for l in f.readlines() if not any(l.startswith(k) for k in ['VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_ADMIN_EMAIL'])]
    
    lines.append(f"VAPID_PUBLIC_KEY={pub_b64}\n")
    lines.append(f"VAPID_PRIVATE_KEY={pem_path}\n")
    lines.append("VAPID_ADMIN_EMAIL=support@nexisrecovery.com\n")
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"Updated {env_file} automatically with your generated VAPID keys.")

if __name__ == '__main__':
    generate_keys()
