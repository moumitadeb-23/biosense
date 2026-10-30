import os
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
    current_app,
)
from flask_login import login_required, current_user

from extensions import db
from database.models import Report, Experiment, AuditLog
from services.report_service import generate_pdf_report
from services.auth_service import role_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@login_required
def index():
    """List all available scientific reports and provide generation controls."""
    if current_user.has_role("ADMIN"):
        reports = Report.query.order_by(Report.created_at.desc()).all()
    else:
        # Show user's reports plus public demo reports
        reports = (
            Report.query.filter(
                (Report.user_id == current_user.id) | (Report.user_id.in_([1]))
            )
            .order_by(Report.created_at.desc())
            .all()
        )

    experiments = Experiment.query.order_by(Experiment.id.desc()).all()
    return render_template("reports/reports.html", reports=reports, experiments=experiments)


@reports_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """Trigger ReportLab PDF generation for a specified experiment."""
    experiment_id = request.form.get("experiment_id", type=int)
    title = request.form.get("title", "").strip()
    include_ml = bool(request.form.get("include_ml"))
    include_anomalies = bool(request.form.get("include_anomalies"))

    if not experiment_id:
        flash("Please select an experiment to generate a scientific report.", "warning")
        return redirect(url_for("reports.index"))

    experiment = Experiment.query.get(experiment_id)
    if not experiment:
        flash(f"Experiment #{experiment_id} not found.", "danger")
        return redirect(url_for("reports.index"))

    result = generate_pdf_report(
        user_id=current_user.id,
        experiment_id=experiment.id,
        title=title if title else None,
        include_ml=include_ml,
        include_anomalies=include_anomalies,
    )

    if result.get("success"):
        flash(f"Report '{result['title']}' generated successfully!", "success")
        return redirect(url_for("reports.view_report", report_id=result["report_id"]))
    else:
        flash(f"Failed to generate report: {result.get('error', 'Unknown error')}", "danger")
        return redirect(url_for("reports.index"))


@reports_bp.route("/<int:report_id>")
@login_required
def view_report(report_id: int):
    """View report metadata, summary, and download options."""
    report = Report.query.get_or_404(report_id)

    # Permission check: own report, or admin, or researcher
    if not (current_user.has_role("ADMIN", "RESEARCHER") or report.user_id == current_user.id):
        abort(403)

    return render_template("reports/view_report.html", report=report)


@reports_bp.route("/download/<int:report_id>")
@login_required
def download(report_id: int):
    """Securely stream the generated PDF file with ownership verification."""
    report = Report.query.get_or_404(report_id)

    # Role & Ownership checks
    if not (current_user.has_role("ADMIN", "RESEARCHER") or report.user_id == current_user.id):
        abort(403)

    if not os.path.exists(report.file_path):
        flash("The requested PDF file could not be found on disk.", "danger")
        return redirect(url_for("reports.index"))

    # Log download action
    audit = AuditLog(
        user_id=current_user.id,
        action="report_downloaded",
        details=f"User downloaded report #{report.id} ({report.filename})",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()

    return send_file(
        report.file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report.filename,
    )


@reports_bp.route("/delete/<int:report_id>", methods=["POST"])
@login_required
def delete(report_id: int):
    """Delete a report record and clean up associated filesystem PDF."""
    report = Report.query.get_or_404(report_id)

    if not (current_user.has_role("ADMIN") or report.user_id == current_user.id):
        abort(403)

    # Clean up physical file safely
    try:
        if os.path.exists(report.file_path):
            os.remove(report.file_path)
    except Exception as e:
        current_app.logger.error(f"Error deleting report file {report.file_path}: {e}")

    db.session.delete(report)
    db.session.commit()

    flash(f"Report #{report_id} has been permanently deleted.", "info")
    return redirect(url_for("reports.index"))
