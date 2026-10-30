import functools
from flask import request, abort, redirect, url_for, flash
from flask_login import current_user
from extensions import db
from database.models import User, AuditLog


def log_audit(action: str, details: str = None, user_id: int = None) -> AuditLog:
    """Record an immutable system audit log event.
    
    Captures user identity, client IP, action keyword, and explanatory metadata.
    """
    try:
        # Determine active user if not explicitly passed
        if user_id is None and current_user and current_user.is_authenticated:
            user_id = current_user.id

        # Determine IP address safely
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) if request else "127.0.0.1"
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry
    except Exception as e:
        db.session.rollback()
        # Non-fatal log failure fallback
        print(f"[AuditLog Error] Failed to write audit event '{action}': {e}")
        return None


def role_required(*allowed_roles: str):
    """Decorator to enforce Role-Based Access Control (RBAC).
    
    Verifies that the current user is authenticated and holds one of the specified roles.
    Raises 403 Forbidden if the user lacks authorization.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to access this scientific resource.", "info")
                return redirect(url_for("auth.login", next=request.path))

            if current_user.role not in allowed_roles:
                log_audit(
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    details=f"User '{current_user.username}' with role '{current_user.role}' attempted to access '{request.path}' requiring {allowed_roles}"
                )
                abort(403)

            return view_func(*args, **kwargs)
        return wrapper
    return decorator
