import pytest
import os
from database.models import MLModel, MLPrediction
from services.ml_service import (
    train_classification_models,
    train_regression_models,
    compute_feature_importance,
    predict_ast,
    ML_NOTICE,
    EXPLAINABILITY_NOTICE,
)
from services.anomaly_service import detect_growth_anomalies


def test_classification_dual_variants(app):
    """Test training classification models with and without zone diameter (target leakage comparison)."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)

        # Variant A: With Zone Diameter (Baseline)
        res_zone = train_classification_models(with_zone=True)
        assert res_zone["success"] is True
        assert res_zone["with_zone"] is True
        assert "Target Leakage Warning" in res_zone["leakage_notice"]
        assert len(res_zone["models"]) == 3
        for name, m in res_zone["models"].items():
            assert 0.0 <= m["accuracy"] <= 1.0
            assert 0.0 <= m["f1_macro"] <= 1.0
            assert len(m["confusion_matrix"]) == 3

        # Variant B: Without Zone Diameter (Genuine Prediction)
        res_no_zone = train_classification_models(with_zone=False)
        assert res_no_zone["success"] is True
        assert res_no_zone["with_zone"] is False
        assert "Genuine Predictive Analysis" in res_no_zone["leakage_notice"]

        # Check database registration
        models_in_db = MLModel.query.all()
        assert len(models_in_db) >= 6


def test_regression_pipeline(app):
    """Test training continuous growth regression estimators (Ridge and Random Forest Regressor)."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)

        res = train_regression_models()
        assert res["success"] is True
        assert "Random Forest Regressor" in res["models"]
        rf = res["models"]["Random Forest Regressor"]
        assert rf["mae"] >= 0.0
        assert rf["rmse"] >= 0.0
        assert len(rf["scatter"]) > 0


def test_feature_importance_and_notices(app):
    """Verify feature importance extraction and strict educational/explainability caveats."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)
        train_classification_models(with_zone=False)

        feat_res = compute_feature_importance("Random Forest")
        assert feat_res["success"] is True
        assert len(feat_res["importances"]) > 0
        assert feat_res["explainability_notice"] == EXPLAINABILITY_NOTICE
        assert feat_res["notice"] == ML_NOTICE


def test_predict_ast_and_db_logging(app):
    """Verify live AST inference and audit logging into ml_predictions table."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)
        train_classification_models(with_zone=False)

        pred = predict_ast(
            organism="Escherichia coli",
            antibiotic="Ampicillin",
            antibiotic_class="beta-lactam",
            concentration=10.0,
            zone_diameter_mm=None
        )
        assert pred["success"] is True
        assert pred["prediction"] in ["S", "I", "R"]
        assert "S" in pred["probabilities"]

        # Verify logged in database
        saved_pred = MLPrediction.query.first()
        assert saved_pred is not None
        assert saved_pred.prediction == pred["prediction"]


def test_detect_growth_anomalies(app):
    """Verify statistical anomaly detection across IQR, Z-Score, and Isolation Forest."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)

        report = detect_growth_anomalies(contamination=0.05)
        assert report["success"] is True
        assert report["total_screened"] > 100
        assert report["total_anomalies"] >= 0
        assert "An anomaly indicates a statistical outlier" in report["notice"]
