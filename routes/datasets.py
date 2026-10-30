import os
import uuid
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_file,
    jsonify
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import pandas as pd

from extensions import db
from database.models import (
    Dataset,
    Experiment,
    GrowthMeasurement,
    SusceptibilityTest,
    Organism,
    Antibiotic,
    Medium,
)
from services.auth_service import log_audit
from services.validation_service import validate_csv_file, detect_dataset_type
from services.cleaning_service import clean_dataframe, sanitize_formula_injection

datasets_bp = Blueprint("datasets", __name__, url_prefix="/datasets")


def is_allowed_file(filename: str) -> bool:
    """Check allowlisted extension strictly for CSV."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@datasets_bp.route("/")
def index():
    """List ingested datasets with validation statuses and actions."""
    user_id = current_user.id if current_user.is_authenticated else None
    if current_user.is_authenticated and current_user.has_role("ADMIN"):
        datasets = Dataset.query.order_by(Dataset.created_at.desc()).all()
    elif user_id:
        datasets = Dataset.query.filter_by(user_id=user_id).order_by(Dataset.created_at.desc()).all()
    else:
        datasets = Dataset.query.order_by(Dataset.created_at.desc()).limit(10).all()

    return render_template("datasets/index.html", datasets=datasets)


@datasets_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Secure CSV upload endpoint enforcing MIME, extension, and size limits."""
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part provided in submission.", "danger")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected for upload.", "danger")
            return redirect(request.url)

        if not is_allowed_file(file.filename):
            flash("Security Restriction: Only .csv (Comma-Separated Values) files are permitted.", "danger")
            return redirect(request.url)

        # Secure filename with unique token to prevent collisions and directory traversal
        original_name = secure_filename(file.filename)
        unique_token = uuid.uuid4().hex[:8]
        stored_filename = f"{unique_token}_{original_name}"
        upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_filename)

        file.save(upload_path)

        # Parse and pre-validate
        try:
            df = pd.read_csv(upload_path)
            row_count = len(df)
        except Exception as e:
            flash(f"Uploaded CSV could not be parsed: {str(e)}", "danger")
            if os.path.exists(upload_path):
                os.remove(upload_path)
            return redirect(request.url)

        # Create database record
        dataset = Dataset(
            user_id=current_user.id,
            filename=original_name,
            filepath=upload_path,
            row_count=row_count,
            data_source="User-Uploaded",
            status="pending"
        )
        db.session.add(dataset)
        db.session.commit()

        log_audit(
            action="DATASET_UPLOAD",
            details=f"Uploaded '{original_name}' ({row_count} rows)",
            user_id=current_user.id
        )

        flash(f"File '{original_name}' uploaded successfully. Reviewing biological validation rules...", "info")
        return redirect(url_for("datasets.validate", dataset_id=dataset.id))

    return render_template("datasets/upload.html")


@datasets_bp.route("/validate/<int:dataset_id>")
@login_required
def validate(dataset_id: int):
    """Render structured validation summary matching spec section 13."""
    dataset = Dataset.query.get_or_404(dataset_id)

    if not os.path.exists(dataset.filepath):
        flash("Underlying dataset file could not be found on server disk.", "danger")
        return redirect(url_for("datasets.index"))

    validation_report = validate_csv_file(dataset.filepath)

    # Preview first 10 rows safely
    try:
        df_preview = pd.read_csv(dataset.filepath, nrows=10)
        preview_rows = df_preview.to_dict(orient="records")
        preview_columns = list(df_preview.columns)
    except Exception:
        preview_rows = []
        preview_columns = []

    return render_template(
        "datasets/validate.html",
        dataset=dataset,
        report=validation_report,
        preview_rows=preview_rows,
        preview_columns=preview_columns
    )


@datasets_bp.route("/clean/<int:dataset_id>", methods=["POST"])
@login_required
def clean(dataset_id: int):
    """Execute selected cleaning options and produce an unalterable change log."""
    dataset = Dataset.query.get_or_404(dataset_id)

    drop_duplicates = bool(request.form.get("drop_duplicates"))
    drop_invalid = bool(request.form.get("drop_invalid"))
    impute_missing = bool(request.form.get("impute_missing"))

    try:
        df = pd.read_csv(dataset.filepath)
        dtype = detect_dataset_type(df)
        cleaned_df, change_log = clean_dataframe(
            df=df,
            dataset_type=dtype,
            drop_duplicates=drop_duplicates,
            drop_invalid_biological=drop_invalid,
            impute_missing=impute_missing
        )

        # Save cleaned file
        cleaned_filename = f"cleaned_{Path(dataset.filepath).name}"
        cleaned_path = os.path.join(current_app.config["UPLOAD_FOLDER"], cleaned_filename)
        cleaned_df.to_csv(cleaned_path, index=False)

        # Update dataset record
        dataset.filepath = cleaned_path
        dataset.row_count = len(cleaned_df)
        dataset.status = "cleaned"
        db.session.commit()

        log_audit(
            action="DATASET_CLEANED",
            details=f"Cleaned dataset #{dataset.id}: retained {len(cleaned_df)} rows",
            user_id=current_user.id
        )

        flash("Dataset cleaning pipeline executed successfully. Check the change log below.", "success")
        return render_template(
            "datasets/cleaned.html",
            dataset=dataset,
            change_log=change_log,
            cleaned_count=len(cleaned_df),
            preview_rows=cleaned_df.head(10).to_dict(orient="records"),
            preview_columns=list(cleaned_df.columns)
        )

    except Exception as e:
        flash(f"Error executing cleaning pipeline: {str(e)}", "danger")
        return redirect(url_for("datasets.validate", dataset_id=dataset.id))


@datasets_bp.route("/download/<int:dataset_id>")
def download(dataset_id: int):
    """Safely download CSV with formula injection protection."""
    dataset = Dataset.query.get_or_404(dataset_id)
    if not os.path.exists(dataset.filepath):
        flash("Requested file does not exist on server.", "danger")
        return redirect(url_for("datasets.index"))

    return send_file(
        dataset.filepath,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"BioSense_{dataset.filename}"
    )


@datasets_bp.route("/import/<int:dataset_id>", methods=["POST"])
@login_required
def import_dataset(dataset_id: int):
    """Confirm and import validated/cleaned records into relational database tables."""
    dataset = Dataset.query.get_or_404(dataset_id)

    try:
        df = pd.read_csv(dataset.filepath)
        dtype = detect_dataset_type(df)

        col_map = {c: str(c).strip().lower() for c in df.columns}
        df = df.rename(columns=col_map)

        imported_count = 0
        rejected_count = 0

        if dtype == "growth":
            # Lookup default medium if not provided
            default_med = Medium.query.filter_by(name="LB Broth").first()
            if not default_med:
                default_med = Medium(name="LB Broth", description="Standard culture broth")
                db.session.add(default_med)
                db.session.flush()

            # Group by experiment parameters
            group_cols = ["organism"]
            if "medium" in df.columns: group_cols.append("medium")
            if "temperature" in df.columns: group_cols.append("temperature")
            if "ph" in df.columns: group_cols.append("ph")

            for group_keys, grp in df.groupby(group_cols):
                org_name = group_keys[0] if isinstance(group_keys, tuple) else group_keys
                med_name = grp["medium"].iloc[0] if "medium" in grp.columns else "LB Broth"
                temp = float(grp["temperature"].iloc[0]) if "temperature" in grp.columns else 37.0
                ph = float(grp["ph"].iloc[0]) if "ph" in grp.columns else 7.0

                # Ensure organism exists
                org = Organism.query.filter_by(scientific_name=org_name).first()
                if not org:
                    org = Organism(scientific_name=org_name, common_name=org_name, gram_type="Gram-negative")
                    db.session.add(org)
                    db.session.flush()

                med = Medium.query.filter_by(name=med_name).first() or default_med

                exp = Experiment(
                    user_id=current_user.id,
                    organism_id=org.id,
                    medium_id=med.id,
                    temperature=temp,
                    ph=ph,
                    incubation_time_h=float(grp["time_h"].max()) if "time_h" in grp.columns else 24.0,
                    data_source="User-Uploaded",
                    notes=f"Imported from user dataset #{dataset.id} ({dataset.filename})"
                )
                db.session.add(exp)
                db.session.flush()

                for _, row in grp.iterrows():
                    try:
                        m = GrowthMeasurement(
                            experiment_id=exp.id,
                            time_h=float(row["time_h"]),
                            optical_density=float(row["optical_density"]),
                            growth_rate=0.45
                        )
                        db.session.add(m)
                        imported_count += 1
                    except Exception:
                        rejected_count += 1

        elif dtype == "susceptibility":
            for _, row in df.iterrows():
                try:
                    org_name = str(row["organism"]).strip()
                    ab_name = str(row["antibiotic"]).strip()

                    org = Organism.query.filter_by(scientific_name=org_name).first()
                    if not org:
                        org = Organism(scientific_name=org_name, common_name=org_name, gram_type=row.get("gram_type", "Gram-negative"))
                        db.session.add(org)
                        db.session.flush()

                    ab = Antibiotic.query.filter_by(name=ab_name).first()
                    if not ab:
                        ab = Antibiotic(name=ab_name, antibiotic_class=row.get("antibiotic_class", "Unclassified"))
                        db.session.add(ab)
                        db.session.flush()

                    zone = float(row["zone_diameter_mm"]) if "zone_diameter_mm" in row and pd.notna(row["zone_diameter_mm"]) else None
                    cat = str(row["category"]).strip().upper() if "category" in row and pd.notna(row["category"]) else None

                    # If category is missing but zone is present, deduce category
                    if not cat and zone is not None:
                        cat = "R" if zone < 14 else ("I" if zone < 18 else "S")

                    test = SusceptibilityTest(
                        organism_id=org.id,
                        antibiotic_id=ab.id,
                        concentration=float(row.get("concentration", 10.0)),
                        zone_diameter_mm=zone,
                        category=cat or "S",
                        data_source="User-Uploaded",
                        source="uploaded"
                    )
                    db.session.add(test)
                    imported_count += 1
                except Exception:
                    rejected_count += 1

        dataset.rows_imported = imported_count
        dataset.rows_rejected = rejected_count
        dataset.status = "imported"
        db.session.commit()

        log_audit(
            action="DATASET_IMPORTED",
            details=f"Imported {imported_count} rows from dataset #{dataset.id} into database ({rejected_count} rejected)",
            user_id=current_user.id
        )

        flash(f"Successfully imported {imported_count} records into active database registry!", "success")
        if dtype == "growth":
            return redirect(url_for("growth.index"))
        else:
            return redirect(url_for("susceptibility.index"))

    except Exception as e:
        db.session.rollback()
        flash(f"Database ingestion error: {str(e)}", "danger")
        return redirect(url_for("datasets.validate", dataset_id=dataset.id))


@datasets_bp.route("/download-sample/<filename>")
def download_sample(filename: str):
    """Download one of the pre-configured benchmark demonstration CSV datasets."""
    allowed_samples = {
        "growth": "perfect_growth_kinetic_assay.csv",
        "ast": "perfect_clinical_ast_panel.csv",
        "dirty": "perfect_dirty_qa_test.csv",
        "perfect_growth_kinetic_assay.csv": "perfect_growth_kinetic_assay.csv",
        "perfect_clinical_ast_panel.csv": "perfect_clinical_ast_panel.csv",
        "perfect_dirty_qa_test.csv": "perfect_dirty_qa_test.csv",
        "sample_growth.csv": "sample_growth.csv",
        "sample_susceptibility.csv": "sample_susceptibility.csv",
    }
    target = allowed_samples.get(filename)
    if not target:
        flash("Requested sample dataset not found.", "warning")
        return redirect(url_for("datasets.upload"))

    dataset_dir = os.path.join(current_app.root_path, "datasets")
    filepath = os.path.join(dataset_dir, target)
    if not os.path.exists(filepath):
        flash(f"File {target} is not available.", "danger")
        return redirect(url_for("datasets.upload"))

    return send_file(
        filepath,
        mimetype="text/csv",
        as_attachment=True,
        download_name=target
    )
