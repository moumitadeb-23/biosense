from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from database.models import User, Organism, Antibiotic, Medium, AuditLog, Experiment, Dataset, MLModel, Report
from services.auth_service import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required("ADMIN")
def index():
    """System administration dashboard showing platform metrics and catalog overview."""
    user_count = User.query.count()
    organism_count = Organism.query.count()
    antibiotic_count = Antibiotic.query.count()
    experiment_count = Experiment.query.count()
    dataset_count = Dataset.query.count()
    report_count = Report.query.count()
    model_count = MLModel.query.count()

    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(15).all()

    return render_template(
        "admin/admin.html",
        user_count=user_count,
        organism_count=organism_count,
        antibiotic_count=antibiotic_count,
        experiment_count=experiment_count,
        dataset_count=dataset_count,
        report_count=report_count,
        model_count=model_count,
        recent_users=recent_users,
        recent_audits=recent_audits,
    )


@admin_bp.route("/audit-logs")
@login_required
@role_required("ADMIN")
def audit_logs():
    """Dedicated full audit logs explorer."""
    page = request.args.get("page", 1, type=int)
    action_filter = request.args.get("action", "")

    query = AuditLog.query
    if action_filter:
        query = query.filter_by(action=action_filter)

    audits = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=25, error_out=False)
    distinct_actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]

    return render_template(
        "admin/audit_logs.html",
        audits=audits,
        action_filter=action_filter,
        distinct_actions=distinct_actions,
    )


@admin_bp.route("/catalog/organisms", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def organisms():
    """Manage reference organisms catalog."""
    if request.method == "POST":
        sci_name = request.form.get("scientific_name", "").strip()
        genus = request.form.get("genus", "").strip()
        species = request.form.get("species", "").strip()
        gram_type = request.form.get("gram_type", "").strip()
        domain_family = request.form.get("domain_family", "").strip()
        description = request.form.get("description", "").strip()

        if not sci_name:
            flash("Scientific name is required.", "danger")
        elif Organism.query.filter_by(scientific_name=sci_name).first():
            flash(f"Organism '{sci_name}' already exists in catalog.", "warning")
        else:
            org = Organism(
                scientific_name=sci_name,
                genus=genus if genus else None,
                species=species if species else None,
                gram_type=gram_type if gram_type else None,
                domain_family=domain_family if domain_family else None,
                description=description if description else None,
            )
            db.session.add(org)

            audit = AuditLog(
                user_id=current_user.id,
                action="admin_catalog_update",
                details=f"Admin added organism '{sci_name}' to reference catalog.",
                ip_address=request.remote_addr,
            )
            db.session.add(audit)
            db.session.commit()
            flash(f"Organism '{sci_name}' added to reference catalog successfully.", "success")

        return redirect(url_for("admin.organisms"))

    all_organisms = Organism.query.order_by(Organism.scientific_name.asc()).all()
    return render_template("admin/organisms.html", organisms=all_organisms)


@admin_bp.route("/catalog/antibiotics", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def antibiotics():
    """Manage reference antibiotics catalog."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        antibiotic_class = request.form.get("antibiotic_class", "").strip()

        if not name or not antibiotic_class:
            flash("Antibiotic name and class are required.", "danger")
        elif Antibiotic.query.filter_by(name=name).first():
            flash(f"Antibiotic '{name}' already exists in catalog.", "warning")
        else:
            ab = Antibiotic(name=name, antibiotic_class=antibiotic_class)
            db.session.add(ab)

            audit = AuditLog(
                user_id=current_user.id,
                action="admin_catalog_update",
                details=f"Admin added antibiotic '{name}' ({antibiotic_class}) to catalog.",
                ip_address=request.remote_addr,
            )
            db.session.add(audit)
            db.session.commit()
            flash(f"Antibiotic '{name}' added to catalog successfully.", "success")

        return redirect(url_for("admin.antibiotics"))

    all_antibiotics = Antibiotic.query.order_by(Antibiotic.name.asc()).all()
    return render_template("admin/antibiotics.html", antibiotics=all_antibiotics)
