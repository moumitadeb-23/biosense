import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from database.models import User, AuditLog


def create_admin_user(username=None, email=None, password=None, force=False, app=None):
    """CLI script to provision the primary platform administrator account."""
    if app is None:
        from flask import current_app
        try:
            if current_app:
                app = current_app._get_current_object()
        except Exception:
            app = None

    if app is None:
        app = create_app()

    with app.app_context():
        # Fallbacks to environment variables
        username = username or os.environ.get("ADMIN_USERNAME", "admin")
        email = email or os.environ.get("ADMIN_EMAIL", "admin@biosense.local")
        password = password or os.environ.get("ADMIN_PASSWORD", "BioSenseAdmin2026!")

        if len(password) < 8:
            print("[ERROR] Administrator password must be at least 8 characters long.")
            sys.exit(1)

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()

        if existing_user:
            if existing_user.role == "ADMIN" and not force:
                print(f"[INFO] Admin user '{username}' already exists with role '{existing_user.role}'.")
                return existing_user

            existing_user.username = username
            existing_user.email = email
            existing_user.role = "ADMIN"
            existing_user.set_password(password)
            db.session.commit()
            print(f"[SUCCESS] Updated existing account '{username}' to role 'ADMIN'.")
            user = existing_user
        else:
            user = User(
                username=username,
                email=email,
                role="ADMIN"
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f"[SUCCESS] Created new Administrator account: '{username}' <{email}>")

        # Record security audit log
        log = AuditLog(
            user_id=user.id,
            action="ADMIN_ACCOUNT_BOOTSTRAPPED",
            details=f"Admin account '{username}' bootstrapped via server CLI script",
            ip_address="127.0.0.1"
        )
        db.session.add(log)
        db.session.commit()
        print("[SUCCESS] Audit event 'ADMIN_ACCOUNT_BOOTSTRAPPED' recorded.")
        return user


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap BioSense Administrator Account")
    parser.add_argument("--username", "-u", default=None, help="Admin username")
    parser.add_argument("--email", "-e", default=None, help="Admin email address")
    parser.add_argument("--password", "-p", default=None, help="Admin password (min 8 chars)")
    parser.add_argument("--force", "-f", action="store_true", help="Force overwrite if user exists")

    args = parser.parse_args()
    create_admin_user(args.username, args.email, args.password, args.force)
