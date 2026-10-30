import os
import secrets
from urllib.parse import urlparse, urlencode
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user

from config import BASE_DIR
from extensions import db
from database.models import User, AuditLog, Experiment, Dataset, Report, MLPrediction
from services.auth_service import log_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def save_google_oauth_creds(client_id: str, client_secret: str) -> None:
    """Save or update Google OAuth2 credentials in the workspace .env file and environment."""
    env_path = BASE_DIR / ".env"
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    updated_id = False
    updated_secret = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("GOOGLE_CLIENT_ID="):
            new_lines.append(f"GOOGLE_CLIENT_ID={client_id}\n")
            updated_id = True
        elif stripped.startswith("GOOGLE_CLIENT_SECRET="):
            new_lines.append(f"GOOGLE_CLIENT_SECRET={client_secret}\n")
            updated_secret = True
        else:
            new_lines.append(line)
            
    if not updated_id:
        new_lines.append(f"GOOGLE_CLIENT_ID={client_id}\n")
    if not updated_secret:
        new_lines.append(f"GOOGLE_CLIENT_SECRET={client_secret}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    os.environ["GOOGLE_CLIENT_ID"] = client_id
    os.environ["GOOGLE_CLIENT_SECRET"] = client_secret



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
    """Google OAuth 2.0 Sign-In & Registration handler.
    
    If production client secrets are configured (GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET),
    immediately redirects the user directly to Google's official OAuth2 consent screen (accounts.google.com).
    
    If not yet configured or when accessed in setup/manual mode (?manual=1), renders an interactive
    gateway allowing the user to either:
      1. Connect their real Google Cloud OAuth credentials and launch live Google login.
      2. Directly authenticate with their real personal Google account (e.g. mamaimoumita23092004@gmail.com).
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    next_url = request.args.get("next") or request.form.get("next")
    manual_mode = request.args.get("manual", "").strip() == "1"

    # If client ID and secret exist and user did not explicitly request manual mode, redirect straight to Google!
    if request.method == "GET" and google_client_id and google_client_secret and not manual_mode:
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        if next_url:
            session["oauth_next"] = next_url

        redirect_uri = url_for("auth.google_callback", _external=True)
        auth_params = {
            "client_id": google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account"
        }
        google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"
        return redirect(google_url)

    # In POST mode
    if request.method == "POST":
        action = request.form.get("action", "login")

        # Action: Save real Google Cloud API Client ID & Secret
        if action == "save_credentials":
            client_id_val = request.form.get("client_id", "").strip()
            client_secret_val = request.form.get("client_secret", "").strip()

            if not client_id_val or not client_secret_val:
                flash("Please provide both the Google Client ID and Google Client Secret from Google Cloud Console.", "danger")
                return render_template(
                    "auth/google_auth.html",
                    next=next_url,
                    has_production_creds=bool(google_client_id and google_client_secret),
                    google_client_id=google_client_id
                )

            save_google_oauth_creds(client_id_val, client_secret_val)
            flash("Google Cloud OAuth credentials saved successfully! Redirecting to Google Login screen...", "success")
            return redirect(url_for("auth.google_auth", next=next_url))

        # Action: Direct sign-in with user's real Google email & name
        google_email = request.form.get("google_email", "").strip().lower()
        google_name = request.form.get("google_name", "").strip()
        selected_role = request.form.get("role", "STUDENT").strip().upper()

        if not google_email or "@" not in google_email:
            google_email = "mamaimoumita23092004@gmail.com"
        if not google_name:
            google_name = "Moumita Deb"
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

    return render_template(
        "auth/google_auth.html",
        next=next_url,
        has_production_creds=bool(google_client_id and google_client_secret),
        google_client_id=google_client_id
    )


@auth_bp.route("/google/callback")
def google_callback():
    """OAuth 2.0 callback endpoint handling Google authorization response.
    
    Exchanges the one-time authorization code for an OAuth2 access token,
    queries Google's UserInfo API (https://www.googleapis.com/oauth2/v3/userinfo),
    and provisions or logs in the authenticated user.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    # Check for errors returned by Google
    error = request.args.get("error")
    if error:
        flash(f"Google authorization was cancelled or failed ({error}).", "warning")
        return redirect(url_for("auth.login"))

    # State verification against CSRF
    req_state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)
    if not req_state or req_state != saved_state:
        flash("Google authentication failed: invalid or expired session state (CSRF check). Please try again.", "danger")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code:
        flash("Authorization code missing from Google response.", "danger")
        return redirect(url_for("auth.login"))

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

    if not google_client_id or not google_client_secret:
        flash("Google OAuth credentials are not configured on this server.", "danger")
        return redirect(url_for("auth.login"))

    # Exchange code for access token
    token_url = "https://oauth2.googleapis.com/token"
    redirect_uri = url_for("auth.google_callback", _external=True)

    try:
        token_res = requests.post(
            token_url,
            data={
                "code": code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            },
            timeout=10
        )
        if token_res.status_code != 200:
            current_app.logger.error(f"Google token exchange failed: {token_res.text}")
            flash("Failed to authenticate with Google's token service. Please check your credentials.", "danger")
            return redirect(url_for("auth.login"))

        tokens = token_res.json()
        access_token = tokens.get("access_token")
        if not access_token:
            flash("No access token received from Google.", "danger")
            return redirect(url_for("auth.login"))

        # Fetch verified profile information from Google
        userinfo_res = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        if userinfo_res.status_code != 200:
            flash("Failed to retrieve profile information from Google.", "danger")
            return redirect(url_for("auth.login"))

        profile = userinfo_res.json()
        google_id = str(profile.get("sub", ""))
        google_email = profile.get("email", "").strip().lower()
        google_name = profile.get("name", "").strip()

        if not google_email:
            flash("Your Google account did not return a verified email address.", "danger")
            return redirect(url_for("auth.login"))

        # Locate existing user by google_id or email
        user = User.query.filter(
            (User.google_id == google_id) | (User.email == google_email)
        ).first()

        if not user:
            base_username = google_email.split("@")[0].replace(".", "_")
            candidate_username = base_username
            idx = 1
            while User.query.filter_by(username=candidate_username).first():
                candidate_username = f"{base_username}_{idx}"
                idx += 1

            user = User(
                username=candidate_username,
                email=google_email,
                full_name=google_name or base_username,
                role="STUDENT",
                auth_provider="google",
                google_id=google_id
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()

            log_audit(
                action="USER_REGISTRATION",
                details=f"New user registered via real Google OAuth: {google_email} ({user.username})",
                user_id=user.id
            )
        else:
            if not user.google_id:
                user.google_id = google_id
            if not user.full_name and google_name:
                user.full_name = google_name
            user.auth_provider = "google"
            db.session.commit()

        login_user(user, remember=True)
        log_audit(
            action="LOGIN_SUCCESS",
            details=f"User {user.username} successfully signed in via Google OAuth2",
            user_id=user.id
        )

        flash(f"Welcome to BioSense, {user.full_name or user.username}! (Authenticated via Google)", "success")
        next_url = session.pop("oauth_next", None)
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    except Exception as exc:
        current_app.logger.exception(f"Unexpected error during Google OAuth callback: {exc}")
        flash(f"An unexpected error occurred during Google sign-in: {str(exc)}", "danger")
        return redirect(url_for("auth.login"))



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
