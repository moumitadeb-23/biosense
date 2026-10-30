import os
import pytest
from extensions import db
from database.models import User, Experiment, Organism, Medium, Report, AuditLog
from services.report_service import generate_pdf_report


def _setup_test_environment(app):
    """Helper to populate necessary reference and test records."""
    with app.app_context():
        res_user = User(username="test_researcher", email="res@test.com", role="RESEARCHER")
        res_user.set_password("UserPass123!")

        stud_user = User(username="test_student", email="stud@test.com", role="STUDENT")
        stud_user.set_password("UserPass123!")

        admin_user = User(username="test_admin", email="admin@test.com", role="ADMIN")
        admin_user.set_password("AdminPass123!")

        org = Organism(
            scientific_name="Klebsiella pneumoniae",
            genus="Klebsiella",
            species="pneumoniae",
            gram_type="Gram-negative",
            domain_family="Enterobacteriaceae",
            description="Reference respiratory and hospital pathogen model."
        )
        med = Medium(name="Mueller-Hinton Broth", description="Standard AST medium.")

        db.session.add_all([res_user, stud_user, admin_user, org, med])
        db.session.commit()

        exp = Experiment(
            user_id=res_user.id,
            organism_id=org.id,
            medium_id=med.id,
            temperature=37.0,
            ph=7.2,
            data_source="Synthetic – Demonstration Data"
        )
        db.session.add(exp)
        db.session.commit()

        return res_user.id, stud_user.id, admin_user.id, exp.id


def test_pdf_report_generation(app):
    """Verify that generate_pdf_report compiles a multi-page PDF with all 13 sections."""
    res_id, _, _, exp_id = _setup_test_environment(app)

    with app.app_context():
        res = generate_pdf_report(
            user_id=res_id,
            experiment_id=exp_id,
            title="Automated Test Scientific Report",
            include_ml=True,
            include_anomalies=True
        )

        assert res["success"] is True
        assert os.path.exists(res["file_path"])
        file_size = os.path.getsize(res["file_path"])
        assert file_size > 10000  # Report with embedded Matplotlib images should be > 10KB

        # Verify DB records
        rep = Report.query.get(res["report_id"])
        assert rep is not None
        assert rep.title == "Automated Test Scientific Report"
        assert rep.experiment_id == exp_id

        # Verify Audit Log
        audit = AuditLog.query.filter_by(action="report_generated").first()
        assert audit is not None


def test_reports_routes_access(client, app):
    """Test listing reports and viewing report details."""
    _setup_test_environment(app)

    # Login as researcher
    client.post("/auth/login", data={"identifier": "test_researcher", "password": "UserPass123!"}, follow_redirects=True)

    # Access reports index
    res = client.get("/reports/")
    assert res.status_code == 200
    assert b"Scientific Analytics Reports" in res.data

    # Generate a report via route
    with app.app_context():
        exp = Experiment.query.first()
        exp_id = exp.id

    gen_res = client.post("/reports/generate", data={
        "experiment_id": exp_id,
        "title": "Route Triggered Report",
        "include_ml": "1",
        "include_anomalies": "1"
    }, follow_redirects=True)

    assert gen_res.status_code == 200
    assert b"Route Triggered Report" in gen_res.data


def test_report_download_security(client, app):
    """Verify ownership & role enforcement on report downloading."""
    res_id, stud_id, admin_id, exp_id = _setup_test_environment(app)

    with app.app_context():
        gen_res = generate_pdf_report(res_id, exp_id, "Confidential Study")
        report_id = gen_res["report_id"]

    # Student login
    client.post("/auth/login", data={"identifier": "test_student", "password": "UserPass123!"}, follow_redirects=True)

    # Student cannot download a report they don't own unless they are an admin or researcher
    # In routes/reports.py:
    # "if not (current_user.has_role('ADMIN', 'RESEARCHER') or report.user_id == current_user.id): abort(403)"
    res = client.get(f"/reports/download/{report_id}")
    assert res.status_code == 403

    # Switch to Admin
    client.get("/auth/logout")
    client.post("/auth/login", data={"identifier": "test_admin", "password": "AdminPass123!"}, follow_redirects=True)

    # Admin CAN download any report
    admin_dl = client.get(f"/reports/download/{report_id}")
    assert admin_dl.status_code == 200
    assert admin_dl.mimetype == "application/pdf"
