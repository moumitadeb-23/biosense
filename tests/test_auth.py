import pytest
from flask import url_for
from database.models import User, AuditLog
from services.auth_service import role_required
from scripts.create_admin import create_admin_user


def test_user_registration_student(client, app):
    """Test successful student account registration via public form."""
    response = client.post("/auth/register", data={
        "username": "student_test",
        "email": "student@biosense.edu",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "role": "STUDENT"
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="student_test").first()
        assert user is not None
        assert user.role == "STUDENT"
        assert user.check_password("Password123!") is True
        assert user.password_hash != "Password123!"

        # Audit log verification
        log = AuditLog.query.filter_by(user_id=user.id, action="USER_REGISTRATION").first()
        assert log is not None


def test_user_registration_researcher(client, app):
    """Test successful researcher account registration."""
    response = client.post("/auth/register", data={
        "username": "researcher_test",
        "email": "researcher@lab.org",
        "password": "ResearchPass123!",
        "confirm_password": "ResearchPass123!",
        "role": "RESEARCHER"
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="researcher_test").first()
        assert user is not None
        assert user.role == "RESEARCHER"


def test_admin_registration_strictly_prevented(client, app):
    """SECURITY TEST: Public registration must reject attempts to self-assign ADMIN role."""
    response = client.post("/auth/register", data={
        "username": "hacker_admin",
        "email": "hacker@domain.com",
        "password": "MaliciousPassword123!",
        "confirm_password": "MaliciousPassword123!",
        "role": "ADMIN"  # Unauthorized role
    }, follow_redirects=True)

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Invalid role selection" in html

    with app.app_context():
        user = User.query.filter_by(username="hacker_admin").first()
        assert user is None  # User was NOT created!

        # Audit log of privilege escalation attempt
        log = AuditLog.query.filter_by(action="PRIVILEGE_ESCALATION_PREVENTED").first()
        assert log is not None


def test_login_success_and_logout(client, app):
    """Test user login with valid credentials and clean session termination."""
    with app.app_context():
        user = User(username="valid_user", email="valid@domain.edu", role="STUDENT")
        user.set_password("MySecretPass123!")
        from extensions import db
        db.session.add(user)
        db.session.commit()

    # Login
    response = client.post("/auth/login", data={
        "identifier": "valid_user",
        "password": "MySecretPass123!"
    }, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Welcome back, valid_user" in html

    # Logout
    logout_resp = client.get("/auth/logout", follow_redirects=True)
    assert logout_resp.status_code == 200
    logout_html = logout_resp.data.decode("utf-8")
    assert "You have been signed out successfully" in logout_html


def test_login_invalid_password(client, app):
    """Test login failure on incorrect password."""
    with app.app_context():
        user = User(username="user_wrong_pw", email="wrong@domain.edu", role="STUDENT")
        user.set_password("CorrectPassword123!")
        from extensions import db
        db.session.add(user)
        db.session.commit()

    response = client.post("/auth/login", data={
        "identifier": "user_wrong_pw",
        "password": "BadPassword999!"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Invalid credentials" in response.data.decode("utf-8")

    with app.app_context():
        log = AuditLog.query.filter_by(action="LOGIN_FAILED").first()
        assert log is not None


def test_cli_create_admin(app):
    """Test bootstrapping an administrator account via the dedicated CLI function."""
    with app.app_context():
        create_admin_user(
            username="cli_admin",
            email="cli_admin@biosense.test",
            password="SecureAdminPass123!",
            app=app
        )
        admin = User.query.filter_by(username="cli_admin").first()
        assert admin is not None
        assert admin.role == "ADMIN"
        assert admin.check_password("SecureAdminPass123!") is True

        log = AuditLog.query.filter_by(action="ADMIN_ACCOUNT_BOOTSTRAPPED", user_id=admin.id).first()
        assert log is not None



def test_user_profile_update(client, app):
    """Test updating user profile information (full name, institution, bio)."""
    with app.app_context():
        user = User(username="profile_user", email="profile@domain.edu", role="STUDENT")
        user.set_password("SecurePass123!")
        from extensions import db
        db.session.add(user)
        db.session.commit()

    # Login
    client.post("/auth/login", data={"identifier": "profile_user", "password": "SecurePass123!"}, follow_redirects=True)

    # View profile
    view_res = client.get("/auth/profile")
    assert view_res.status_code == 200
    assert b"Account & Researcher Profile" in view_res.data

    # Update profile
    update_res = client.post("/auth/profile/update", data={
        "full_name": "Dr. Aditi Sharma",
        "institution": "BCA Bioinformatics Laboratory",
        "research_focus": "Microbial Kinetics and AMR Prediction",
        "bio": "Conducting final-year data science research on antibiotic breakpoints."
    }, follow_redirects=True)

    assert update_res.status_code == 200
    assert b"successfully updated" in update_res.data

    with app.app_context():
        u = User.query.filter_by(username="profile_user").first()
        assert u.full_name == "Dr. Aditi Sharma"
        assert u.institution == "BCA Bioinformatics Laboratory"
        assert u.research_focus == "Microbial Kinetics and AMR Prediction"
        assert "antibiotic breakpoints" in u.bio


def test_user_change_password(client, app):
    """Test changing user password securely."""
    with app.app_context():
        user = User(username="pw_changer", email="pw@domain.edu", role="RESEARCHER")
        user.set_password("OriginalPassword123!")
        from extensions import db
        db.session.add(user)
        db.session.commit()

    # Login
    client.post("/auth/login", data={"identifier": "pw_changer", "password": "OriginalPassword123!"}, follow_redirects=True)

    # Attempt change with wrong current password
    fail_res = client.post("/auth/profile/change-password", data={
        "current_password": "WrongPassword999!",
        "new_password": "NewSecretPassword123!",
        "confirm_new_password": "NewSecretPassword123!"
    }, follow_redirects=True)
    assert fail_res.status_code == 200
    assert b"Current password is incorrect" in fail_res.data

    # Change with correct current password
    success_res = client.post("/auth/profile/change-password", data={
        "current_password": "OriginalPassword123!",
        "new_password": "NewSecretPassword123!",
        "confirm_new_password": "NewSecretPassword123!"
    }, follow_redirects=True)
    assert success_res.status_code == 200
    assert b"password has been changed successfully" in success_res.data

    with app.app_context():
        u = User.query.filter_by(username="pw_changer").first()
        assert u.check_password("NewSecretPassword123!") is True
        assert u.check_password("OriginalPassword123!") is False


def test_google_oauth_workflow(client, app):
    """Test Google Identity Services sign-in and user provisioning."""
    # GET Google auth page
    get_res = client.get("/auth/google")
    assert get_res.status_code == 200
    assert b"Google Identity Services" in get_res.data

    # POST to authenticate via Google
    auth_res = client.post("/auth/google", data={
        "google_email": "scholar.google@gmail.com",
        "google_name": "Google Scholar Student",
        "role": "STUDENT"
    }, follow_redirects=True)

    assert auth_res.status_code == 200
    assert b"Signed in with Google" in auth_res.data or b"Dashboard" in auth_res.data

    with app.app_context():
        u = User.query.filter_by(email="scholar.google@gmail.com").first()
        assert u is not None
        assert u.auth_provider == "google"
        assert u.full_name == "Google Scholar Student"
        assert u.role == "STUDENT"


def test_register_admin_portal_workflow_and_login(client, app):
    """Test dedicated Administrator Registration portal, passkey validation, and administrative login."""
    # 1. GET admin registration portal
    get_res = client.get("/auth/register-admin")
    assert get_res.status_code == 200
    assert b"Administrator Registration Portal" in get_res.data
    assert b"admin_passkey" in get_res.data

    # 2. POST with correct passkey to register new admin
    reg_res = client.post("/auth/register-admin", data={
        "username": "portal_admin",
        "email": "portal_admin@biosense.edu",
        "full_name": "Dr. Portal Administrator",
        "institution": "Central Laboratory Governance",
        "admin_passkey": "biosense-admin-2026",
        "password": "MasterAdminPass123!",
        "confirm_password": "MasterAdminPass123!"
    }, follow_redirects=True)

    assert reg_res.status_code == 200
    assert b"Administrator account successfully provisioned" in reg_res.data

    with app.app_context():
        admin = User.query.filter_by(username="portal_admin").first()
        assert admin is not None
        assert admin.role == "ADMIN"
        assert admin.full_name == "Dr. Portal Administrator"
        assert admin.institution == "Central Laboratory Governance"
        assert admin.check_password("MasterAdminPass123!") is True

        # Verify audit log
        log = AuditLog.query.filter_by(action="ADMIN_REGISTRATION", user_id=admin.id).first()
        assert log is not None

    # 3. Log in with the newly registered administrator credentials
    login_res = client.post("/auth/login", data={
        "identifier": "portal_admin",
        "password": "MasterAdminPass123!"
    }, follow_redirects=True)

    assert login_res.status_code == 200
    assert b"Welcome back, Dr. Portal Administrator (ADMIN)" in login_res.data
    # Admin is redirected to Admin Control Panel
    assert b"Admin Control Panel" in login_res.data or b"System Administration" in login_res.data or b"admin" in login_res.data

    # 4. Access protected Admin route
    admin_dash_res = client.get("/admin/")
    assert admin_dash_res.status_code == 200
    assert b"System Administration" in admin_dash_res.data or b"admin" in admin_dash_res.data


def test_register_admin_invalid_passkey_prevented(client, app):
    """Test that administrator registration fails if authorization passkey is incorrect."""
    res = client.post("/auth/register-admin", data={
        "username": "unauthorized_admin",
        "email": "unauth@domain.com",
        "full_name": "Fake Admin",
        "admin_passkey": "WrongPasskey999!",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Invalid Administrator Authorization Passkey" in res.data

    with app.app_context():
        user = User.query.filter_by(username="unauthorized_admin").first()
        assert user is None  # Account was NOT created!

        log = AuditLog.query.filter_by(action="INVALID_ADMIN_PASSKEY").first()
        assert log is not None


def test_google_oauth_save_credentials_flow(client):
    """Test saving Google Cloud OAuth credentials via the gateway UI."""
    res = client.post("/auth/google", data={
        "action": "save_credentials",
        "client_id": "test-mock-id.apps.googleusercontent.com",
        "client_secret": "test-mock-secret-1234"
    }, follow_redirects=False)

    assert res.status_code == 302
    assert "/auth/google" in res.headers["Location"]


def test_google_oauth_callback_requires_state_validation(client):
    """Test that the Google OAuth callback rejects requests with missing or mismatched CSRF state."""
    # Attempt callback without state
    res = client.get("/auth/google/callback?code=mock_auth_code_123", follow_redirects=True)
    assert res.status_code == 200
    assert b"invalid or expired session state" in res.data or b"Sign In" in res.data


