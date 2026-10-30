import os
import io
import pytest
import pandas as pd
from pathlib import Path
from services.validation_service import validate_csv_file, validate_growth_dataframe
from services.cleaning_service import clean_dataframe, sanitize_formula_injection
from database.models import User, Dataset, Experiment, GrowthMeasurement


def test_validation_clean_growth_data():
    """Verify that the generated sample_growth.csv passes biological validation."""
    csv_path = Path(__file__).resolve().parent.parent / "datasets" / "sample_growth.csv"
    assert csv_path.exists()

    report = validate_csv_file(str(csv_path))
    assert report["dataset_type"] == "growth"
    assert report["is_valid"] is True
    assert report["total_rows"] == 1950
    assert report["invalid_rows"] == 0
    assert len(report["errors"]) == 0


def test_validation_detects_dirty_growth_errors():
    """Verify that the dirty test file accurately detects negative OD and impossible pH."""
    dirty_path = Path(__file__).resolve().parent.parent / "datasets" / "sample_dirty_growth.csv"
    assert dirty_path.exists()

    report = validate_csv_file(str(dirty_path))
    assert report["dataset_type"] == "growth"
    assert report["is_valid"] is False
    assert report["invalid_rows"] > 0
    assert report["duplicate_rows"] > 0

    error_reasons = [e["reason"] for e in report["errors"]]
    assert any("Negative Optical Density" in r for r in error_reasons)
    assert any("biological spectrum" in r for r in error_reasons)


def test_cleaning_service_produces_detailed_change_log():
    """Verify that clean_dataframe purges errors and returns an audit trail."""
    raw_data = {
        "organism": ["Escherichia coli", "Escherichia coli", "Escherichia coli", "Staphylococcus aureus"],
        "time_h": [0.0, 0.0, 2.0, 4.0],
        "optical_density": [0.05, 0.05, -0.20, 0.85],  # Contains 1 duplicate and 1 negative OD
        "ph": [7.0, 7.0, 7.0, 99.0]                     # Contains 1 impossible pH
    }
    df = pd.DataFrame(raw_data)

    cleaned_df, change_log = clean_dataframe(
        df=df,
        dataset_type="growth",
        drop_duplicates=True,
        drop_invalid_biological=True,
        impute_missing=False
    )

    assert len(cleaned_df) == 1  # Only row 0 (or deduped row 1) survives!
    assert cleaned_df.iloc[0]["organism"] == "Escherichia coli"
    assert cleaned_df.iloc[0]["optical_density"] == 0.05

    # Check change log items
    log_text = " ".join(change_log)
    assert "duplicate" in log_text.lower()
    assert "negative od600" in log_text.lower()
    assert "ph" in log_text.lower()


def test_formula_injection_sanitization():
    """SECURITY TEST: Neutralize Excel/LibreOffice formula injection characters."""
    dangerous_df = pd.DataFrame({
        "organism": ["=cmd|' /C calc'!A0", "+SUM(A1:A10)", "@macro", "-10", "Safe Bacteria"]
    })
    sanitized_df, neutralized = sanitize_formula_injection(dangerous_df)

    assert neutralized == 4
    for i in range(4):
        val = str(sanitized_df.iloc[i]["organism"])
        assert val.startswith("'")

    assert sanitized_df.iloc[4]["organism"] == "Safe Bacteria"


def test_upload_and_import_http_flow(client, app):
    """Integration test: upload CSV via HTTP, clean, and import into database."""
    with app.app_context():
        user = User(username="data_user", email="data_user@test.org", role="STUDENT")
        user.set_password("SecurePass123!")
        from extensions import db
        db.session.add(user)
        db.session.commit()
        uid = user.id

    # Authenticate
    client.post("/auth/login", data={"identifier": "data_user", "password": "SecurePass123!"})

    # Prepare small test CSV
    csv_content = (
        "organism,time_h,optical_density,temperature,ph,medium\n"
        "Bacillus subtilis,0.0,0.04,37.0,7.0,LB Broth\n"
        "Bacillus subtilis,2.0,0.12,37.0,7.0,LB Broth\n"
        "Bacillus subtilis,4.0,0.48,37.0,7.0,LB Broth\n"
    )
    data = {
        "file": (io.BytesIO(csv_content.encode("utf-8")), "microbe_test.csv")
    }

    # Upload
    upload_resp = client.post("/datasets/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert upload_resp.status_code == 200
    assert "Validation Report" in upload_resp.data.decode("utf-8") or "Biological Validation Summary" in upload_resp.data.decode("utf-8")

    with app.app_context():
        ds = Dataset.query.filter_by(filename="microbe_test.csv").first()
        assert ds is not None
        ds_id = ds.id

    # Confirm Import
    import_resp = client.post(f"/datasets/import/{ds_id}", follow_redirects=True)
    assert import_resp.status_code == 200

    with app.app_context():
        exp = Experiment.query.filter_by(user_id=uid).first()
        assert exp is not None
        assert exp.organism.scientific_name == "Bacillus subtilis"
        assert len(exp.growth_measurements) == 3
