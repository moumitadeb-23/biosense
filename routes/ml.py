from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import current_user
from database.models import MLModel, MLPrediction, Organism, Antibiotic, Medium
from services.ml_service import (
    train_classification_models,
    train_regression_models,
    compute_feature_importance,
    predict_ast,
    ML_NOTICE,
    EXPLAINABILITY_NOTICE,
)
from services.anomaly_service import detect_growth_anomalies

ml_bp = Blueprint("ml", __name__, url_prefix="/ml")


@ml_bp.route("/")
def index():
    """Machine Learning Laboratory - Classification suite."""
    organisms = Organism.query.order_by(Organism.scientific_name).all()
    antibiotics = Antibiotic.query.order_by(Antibiotic.name).all()
    models = MLModel.query.filter(MLModel.model_type.like("classification%")).all()

    return render_template(
        "ml/classification.html",
        organisms=organisms,
        antibiotics=antibiotics,
        models=models,
        ml_notice=ML_NOTICE
    )


@ml_bp.route("/train-classification", methods=["POST"])
def train_classification():
    """Train classification models dynamically and compute all evaluation metrics."""
    data = request.get_json() or request.form
    with_zone = str(data.get("with_zone", "true")).lower() == "true"
    result = train_classification_models(with_zone=with_zone)
    return jsonify(result)


@ml_bp.route("/regression")
def regression():
    """Growth kinetics regression suite predicting optical density."""
    organisms = Organism.query.order_by(Organism.scientific_name).all()
    media = Medium.query.order_by(Medium.name).all()
    models = MLModel.query.filter_by(model_type="regression").all()

    return render_template(
        "ml/regression.html",
        organisms=organisms,
        media=media,
        models=models,
        ml_notice=ML_NOTICE
    )


@ml_bp.route("/train-regression", methods=["POST"])
def train_regression():
    """Train continuous regression models dynamically."""
    result = train_regression_models()
    return jsonify(result)


@ml_bp.route("/compare")
def compare():
    """Dynamic model comparison matrix displaying all computed evaluation metrics."""
    models = MLModel.query.all()
    return render_template("ml/compare.html", models=models, ml_notice=ML_NOTICE)


@ml_bp.route("/explain")
def explain():
    """Feature importance and model interpretability dashboard."""
    importance_data = compute_feature_importance("Random Forest")
    return render_template(
        "ml/explain.html",
        data=importance_data,
        ml_notice=ML_NOTICE,
        explain_notice=EXPLAINABILITY_NOTICE
    )


@ml_bp.route("/predict-ast", methods=["POST"])
def predict_endpoint():
    """Live inference prediction endpoint storing predictions into ml_predictions table."""
    data = request.get_json() or request.form
    org = data.get("organism")
    ab = data.get("antibiotic")
    ab_class = data.get("antibiotic_class", "beta-lactam")
    conc = float(data.get("concentration", 10.0))
    zone = float(data.get("zone_diameter_mm")) if data.get("zone_diameter_mm") else None

    uid = current_user.id if current_user.is_authenticated else None

    result = predict_ast(
        organism=org,
        antibiotic=ab,
        antibiotic_class=ab_class,
        concentration=conc,
        zone_diameter_mm=zone,
        user_id=uid
    )
    return jsonify(result)


@ml_bp.route("/anomaly")
def anomaly():
    """Statistical outlier and culture contamination anomaly screening dashboard."""
    report = detect_growth_anomalies(contamination=0.05)
    return render_template("ml/anomaly.html", report=report, ml_notice=ML_NOTICE)


@ml_bp.route("/api/anomalies")
def api_anomalies():
    """JSON API for anomaly screening."""
    return jsonify(detect_growth_anomalies())
