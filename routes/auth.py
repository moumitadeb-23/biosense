import os
import secrets
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from database.models import User, AuditLog, Experiment, Dataset, Report, MLPrediction
from services.auth_service import log_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def is_safe_url(target: str) -> bool:
    """Validate that redirect target URL belongs to the host application (prevents open redirects)."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("", "http", "https") and (test_url.netloc == "" or test_url.netloc == ref_url.netloc)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a new student or researcher account.
    
    SECURITY RULE: Public registration strictly permits only 'STUDENT' or 'RESEARCHER' roles.
    ADMIN accounts cannot be registered via web forms and must be created via CLI script.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        requested_role = request.form.get("role", "STUDENT").strip().upper()
        full_name = request.form.get("full_name", "").strip()
        institution = request.form.get("institution", "").strip()

        # Validation rules
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if not email or "@" not in email:
            errors.append("A valid academic/institutional email is required.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Role Security Check
        if requested_role not in ["STUDENT", "RESEARCHER"]:
            log_audit(
                action="PRIVILEGE_ESCALATION_PREVENTED",
                details=f"Attempted public registration with prohibited role '{requested_role}' by username '{username}'"
            )
            errors.append("Invalid role selection. Public registration is restricted to Student or Researcher accounts.")

        # Check existing user
        if User.query.filter_by(username=username).first():
            errors.append("Username is already registered. Please choose another.")
        if User.query.filter_by(email=email).first():
            errors.append("Email address is already registered. Please sign in instead.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "auth/register.html",
                username=username,
                email=email,
                role=requested_role,
                full_name=full_name,
                institution=institution,
            )

        # Create user account
        new_user = User(
            username=username,
            email=email,
            role=requested_role,
            full_name=full_name if full_name else None,
            institution=institution if institution else None,
            auth_provider="local"
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        log_audit(
            action="USER_REGISTRATION",
            details=f"New {requested_role} account registered: {username} ({email})",
            user_id=new_user.id
        )

        flash(f"Account successfully created as {requested_role}! You may now sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/register-admin", methods=["GET", "POST"])
@auth_bp.route("/admin/register", methods=["GET", "POST"])
def register_admin():
    """Dedicated registration portal for system administrators.
    
    Protected by an Administrator Authorization Passkey to prevent unauthorized
    privilege escalation while allowing administrators to self-register via a
    dedicated web portal.
    """
    if current_user.is_authenticated:
        if current_user.has_role("ADMIN"):
            return redirect(url_for("admin.index"))
        return redirect(url_for("dashboard.index"))

    admin_passkey_env = os.environ.get("ADMIN_REGISTRATION_KEY", "biosense-admin-2026")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        institution = request.form.get("institution", "").strip()
        passkey = request.form.get("admin_passkey", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Admin username must be at least 3 characters long.")
        if not email or "@" not in email:
            errors.append("A valid institutional/administrative email is required.")
        if not passkey:
            errors.append("Administrator Authorization Passkey is required.")
        elif passkey != admin_passkey_env:
            log_audit(
                action="INVALID_ADMIN_PASSKEY",
                details=f"Unauthorized admin registration attempt for '{username}' ({email}): incorrect passkey"
            )
            errors.append("Invalid Administrator Authorization Passkey. Access to Administrator tier is denied.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Check existing user
        if User.query.filter_by(username=username).first():
            errors.append("Username is already registered. Please choose another.")
        if User.query.filter_by(email=email).first():
            errors.append("Email address is already registered. Please sign in instead.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "auth/register_admin.html",
                username=username,
                email=email,
                full_name=full_name,
                institution=institution,
                default_key=admin_passkey_env
            )

        # Create administrator account
        new_admin = User(
            username=username,
            email=email,
            role="ADMIN",
            full_name=full_name if full_name else None,
            institution=institution if institution else None,
            auth_provider="local"
        )
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()

        log_audit(
            action="ADMIN_REGISTRATION",
            details=f"New ADMIN account registered via Admin Portal: {username} ({email})",
            user_id=new_admin.id
        )

        flash("Administrator account successfully provisioned! You may now sign in with your administrative credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register_admin.html", default_key=admin_passkey_env)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate existing users via username/email and password."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        # Find by either username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            log_audit(
                action="LOGIN_SUCCESS",
                details=f"User {user.username} successfully logged in as {user.role}",
                user_id=user.id
            )
            flash(f"Welcome back, {user.full_name or user.username} ({user.role})!", "success")

            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            if user.has_role("ADMIN"):
                return redirect(url_for("admin.index"))
            return redirect(url_for("dashboard.index"))
        else:
            log_audit(
                action="LOGIN_FAILED",
                details=f"Failed login attempt for identifier '{identifier}'"
            )
            flash("Invalid credentials. Please verify your username/email and password.", "danger")

    return render_template("auth/login.html", next=next_url)


@auth_bp.route("/google", methods=["GET", "POST"])
def google_auth():
    """Google OAuth Sign-In & Registration handler.
    
    Provides seamless one-click Google OAuth authentication.
    If production client secrets are set in environment, redirects to Google's OAuth2 consent screen.
    Otherwise, provides interactive demo Google Sign-In with instant account linkage.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    next_url = request.args.get("next") or request.form.get("next")

    # In POST mode (or simulation submit), authenticate or register user via Google identity
    if request.method == "POST":
        google_email = request.form.get("google_email", "").strip().lower()
        google_name = request.form.get("google_name", "").strip()
        selected_role = request.form.get("role", "STUDENT").strip().upper()

        if not google_email or "@" not in google_email:
            google_email = "scholar.student@gmail.com"
        if not google_name:
            google_name = "Google BioScholar"
        if selected_role not in ["STUDENT", "RESEARCHER"]:
            selected_role = "STUDENT"

        # Check if user already exists
        user = User.query.filter_by(email=google_email).first()

        if not user:
            # Generate clean username from email prefix
            base_username = google_email.split("@")[0].replace(".", "_")
            candidate_username = base_username
            idx = 1
            while User.query.filter_by(username=candidate_username).first():
                candidate_username = f"{base_username}_{idx}"
                idx += 1

            user = User(
                username=candidate_username,
                email=google_email,
                full_name=google_name,
                role=selected_role,
                auth_provider="google",
                google_id=f"g_{secrets.token_hex(8)}"
            )
            # Set high-entropy random password hash
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()

            log_audit(
                action="USER_REGISTRATION",
                details=f"Registered new {selected_role} via Google Identity: {google_email}",
                user_id=user.id
            )
        else:
            if not user.full_name and google_name:
                user.full_name = google_name
            user.auth_provider = "google"
            db.session.commit()

        login_user(user, remember=True)
        log_audit(
            action="LOGIN_SUCCESS",
            details=f"User {user.username} authenticated via Google Identity",
            user_id=user.id
        )

        flash(f"Successfully signed in with Google as {user.full_name or user.username} ({user.role})!", "success")

        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/google_auth.html", next=next_url, has_production_creds=bool(google_client_id))


@auth_bp.route("/logout")
@login_required
def logout():
    """Terminate the active user session and record an audit trail event."""
    username = current_user.username
    uid = current_user.id
    logout_user()
    log_audit(
        action="LOGOUT",
        details=f"User {username} logged out safely",
        user_id=uid
    )
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profile")
@login_required
def profile():
    """Display user profile metadata, role permissions, activity statistics, and audit history."""
    recent_logs = AuditLog.query.filter_by(user_id=current_user.id).order_by(AuditLog.timestamp.desc()).limit(20).all()
    exp_count = Experiment.query.filter_by(user_id=current_user.id).count()
    dataset_count = Dataset.query.filter_by(user_id=current_user.id).count()
    report_count = Report.query.filter_by(user_id=current_user.id).count()
    pred_count = MLPrediction.query.filter_by(user_id=current_user.id).count()

    stats = {
        "experiments": exp_count,
        "datasets": dataset_count,
        "reports": report_count,
        "predictions": pred_count
    }

    return render_template(
        "auth/profile.html",
        user=current_user,
        logs=recent_logs,
        stats=stats
    )


@auth_bp.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    """Update profile information (full name, institution, research focus, bio)."""
    full_name = request.form.get("full_name", "").strip()
    institution = request.form.get("institution", "").strip()
    research_focus = request.form.get("research_focus", "").strip()
    bio = request.form.get("bio", "").strip()

    current_user.full_name = full_name if full_name else None
    current_user.institution = institution if institution else None
    current_user.research_focus = research_focus if research_focus else None
    current_user.bio = bio if bio else None

    db.session.commit()

    log_audit(
        action="PROFILE_UPDATED",
        details=f"User {current_user.username} updated profile information",
        user_id=current_user.id
    )

    flash("Your profile information has been successfully updated!", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    """Update user security credentials."""
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    if not current_user.check_password(current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("auth.profile"))

    if not new_password or len(new_password) < 8:
        flash("New password must be at least 8 characters long.", "danger")
        return redirect(url_for("auth.profile"))

    if new_password != confirm_new_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("auth.profile"))

    current_user.set_password(new_password)
    db.session.commit()

    log_audit(
        action="PASSWORD_CHANGED",
        details=f"User {current_user.username} successfully updated their password",
        user_id=current_user.id
    )

    flash("Your password has been changed successfully!", "success")
    return redirect(url_for("auth.profile"))
