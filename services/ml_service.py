import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.inspection import permutation_importance
from flask import current_app

from extensions import db
from database.models import (
    SusceptibilityTest,
    GrowthMeasurement,
    Experiment,
    Organism,
    Antibiotic,
    Medium,
    MLModel,
    MLPrediction,
)
from services.auth_service import log_audit

ML_NOTICE = "This model provides predictions based on the training dataset and is intended for educational/research purposes only."
EXPLAINABILITY_NOTICE = "Feature importance reflects statistical associations within the trained model, not proven biological causation."


def get_model_storage_dir() -> str:
    """Retrieve absolute path for safe model storage."""
    folder = current_app.config.get("MODEL_FOLDER", "models") if current_app else "models"
    os.makedirs(folder, exist_ok=True)
    return folder


def is_safe_model_path(filepath: str) -> bool:
    """Verify that model file strictly resides within the authorized models directory."""
    storage_dir = os.path.abspath(get_model_storage_dir())
    target_path = os.path.abspath(filepath)
    return target_path.startswith(storage_dir) and os.path.exists(target_path)


def train_classification_models(with_zone: bool = True) -> Dict[str, Any]:
    """Train multi-class AST classification models with pipeline preprocessing.
    
    with_zone=True serves as a rule-reproduction baseline (target leakage demonstration).
    with_zone=False serves as the genuine predictive model.
    """
    tests = SusceptibilityTest.query.all()
    if len(tests) < 25:
        return {
            "success": False,
            "error": f"Insufficient data: {len(tests)} observations found (minimum 25 required to train classifiers).",
            "warning": "Please seed demo data or upload an AST dataset."
        }

    data = []
    for t in tests:
        if not t.category or t.category not in ["S", "I", "R"]:
            continue
        data.append({
            "organism": t.organism.scientific_name,
            "antibiotic": t.antibiotic.name,
            "antibiotic_class": t.antibiotic.antibiotic_class,
            "concentration": float(t.concentration) if t.concentration else 10.0,
            "zone_diameter_mm": float(t.zone_diameter_mm) if t.zone_diameter_mm else 0.0,
            "category": t.category
        })

    df = pd.DataFrame(data)
    if len(df) < 25 or df["category"].nunique() < 2:
        return {
            "success": False,
            "error": "Dataset must contain at least 25 valid records and at least 2 distinct AST categories."
        }

    # Feature selection
    categorical_features = ["organism", "antibiotic", "antibiotic_class"]
    numeric_features = ["concentration"]
    if with_zone:
        numeric_features.append("zone_diameter_mm")

    all_features = categorical_features + numeric_features
    X = df[all_features]
    y = df["category"]

    # Stratified Train-Test Split (80/20) with fixed random seed
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Preprocessing Pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            ]), categorical_features),
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ]), numeric_features)
        ]
    )

    # Algorithms
    classifiers = {
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "Decision Tree": DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42)
    }

    storage_dir = get_model_storage_dir()
    variant_slug = "classification_zone" if with_zone else "classification_no_zone"
    variant_label = "Rule-Reproduction Baseline (With Zone Diameter)" if with_zone else "Genuine Predictive Model (No Zone Diameter)"

    model_results = {}
    classes = ["S", "I", "R"]

    for name, clf in classifiers.items():
        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", clf)
        ])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_test, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()

        filename = f"{variant_slug}_{name.lower().replace(' ', '_')}.joblib"
        filepath = os.path.join(storage_dir, filename)
        joblib.dump(pipe, filepath)

        metrics = {
            "accuracy": round(float(acc), 4),
            "precision_macro": round(float(prec), 4),
            "recall_macro": round(float(rec), 4),
            "f1_macro": round(float(f1), 4),
            "confusion_matrix": cm,
            "classes": classes,
            "test_size": len(y_test),
            "train_size": len(y_train)
        }
        model_results[name] = metrics

        # Register in database ml_models table
        record_name = f"{name} ({'Zone' if with_zone else 'No Zone'})"
        db_model = MLModel.query.filter_by(name=record_name).first()
        if not db_model:
            db_model = MLModel(
                name=record_name,
                model_type=variant_slug,
                algorithm=name,
                target="category (S/I/R)",
                features_json=json.dumps(all_features),
                metrics_json=json.dumps(metrics),
                file_path=filepath
            )
            db.session.add(db_model)
        else:
            db_model.metrics_json = json.dumps(metrics)
            db_model.file_path = filepath
        db.session.commit()

    log_audit(
        action="MODEL_TRAINED",
        details=f"Trained {len(classifiers)} classification models for variant '{variant_slug}'"
    )

    return {
        "success": True,
        "variant": variant_slug,
        "variant_label": variant_label,
        "with_zone": with_zone,
        "models": model_results,
        "notice": ML_NOTICE,
        "leakage_notice": "Target Leakage Warning: Models trained with zone diameter directly mirror clinical breakpoint thresholds and achieve near-perfect scores because zone diameter encodes the target." if with_zone else "Genuine Predictive Analysis: Models trained without zone diameter rely on pre-experimental biological features."
    }


def train_regression_models() -> Dict[str, Any]:
    """Train continuous growth regression models predicting optical density (OD600)."""
    measurements = (
        db.session.query(
            GrowthMeasurement.time_h,
            GrowthMeasurement.optical_density,
            Organism.scientific_name,
            Medium.name,
            Experiment.temperature,
            Experiment.ph
        )
        .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
        .join(Organism, Experiment.organism_id == Organism.id)
        .join(Medium, Experiment.medium_id == Medium.id)
        .all()
    )

    if len(measurements) < 40:
        return {
            "success": False,
            "error": f"Insufficient growth measurements: {len(measurements)} found (minimum 40 required for regression)."
        }

    df = pd.DataFrame(measurements, columns=["time_h", "od", "organism", "medium", "temperature", "ph"])

    categorical_features = ["organism", "medium"]
    numeric_features = ["time_h", "temperature", "ph"]
    all_features = categorical_features + numeric_features

    X = df[all_features]
    y = df["od"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            ]), categorical_features),
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ]), numeric_features)
        ]
    )

    regressors = {
        "Ridge Regression": Ridge(alpha=1.0, random_state=42),
        "Random Forest Regressor": RandomForestRegressor(n_estimators=100, random_state=42)
    }

    storage_dir = get_model_storage_dir()
    model_results = {}

    for name, reg in regressors.items():
        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("regressor", reg)
        ])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = float(np.sqrt(mse))
        r2 = r2_score(y_test, y_pred)

        # Actual vs Predicted scatter points (sample 60 points for visualization)
        sample_indices = np.random.choice(len(y_test), min(60, len(y_test)), replace=False)
        scatter_points = [
            {"actual": round(float(y_test.iloc[i]), 3), "predicted": round(float(y_pred[i]), 3)}
            for i in sample_indices
        ]

        filename = f"regression_{name.lower().replace(' ', '_')}.joblib"
        filepath = os.path.join(storage_dir, filename)
        joblib.dump(pipe, filepath)

        metrics = {
            "mae": round(float(mae), 4),
            "mse": round(float(mse), 4),
            "rmse": round(float(rmse), 4),
            "r2_score": round(float(r2), 4),
            "scatter": scatter_points,
            "test_size": len(y_test),
            "train_size": len(y_train)
        }
        model_results[name] = metrics

        db_model = MLModel.query.filter_by(name=name).first()
        if not db_model:
            db_model = MLModel(
                name=name,
                model_type="regression",
                algorithm=name,
                target="optical_density (OD600)",
                features_json=json.dumps(all_features),
                metrics_json=json.dumps(metrics),
                file_path=filepath
            )
            db.session.add(db_model)
        else:
            db_model.metrics_json = json.dumps(metrics)
            db_model.file_path = filepath
        db.session.commit()

    log_audit(
        action="MODEL_TRAINED",
        details=f"Trained {len(regressors)} regression models for OD600 prediction"
    )

    return {
        "success": True,
        "models": model_results,
        "notice": ML_NOTICE
    }


def compute_feature_importance(model_name: str = "Random Forest") -> Dict[str, Any]:
    """Calculate tree-based and permutation feature importance for model explainability."""
    db_model = MLModel.query.filter(MLModel.name.ilike(f"%{model_name}%")).first()
    if not db_model or not is_safe_model_path(db_model.file_path):
        return {
            "success": False,
            "error": f"Trained model '{model_name}' not found. Please train models first."
        }

    pipeline = joblib.load(db_model.file_path)
    preprocessor = pipeline.named_steps.get("preprocessor")
    estimator = pipeline.named_steps.get("classifier") or pipeline.named_steps.get("regressor")

    if not hasattr(estimator, "feature_importances_"):
        return {
            "success": False,
            "error": "Estimator does not provide tree-based feature importances."
        }

    # Extract transformed feature names
    cat_encoder = preprocessor.named_transformers_["cat"].named_steps["encoder"]
    cat_cols = cat_encoder.get_feature_names_out().tolist()
    num_cols = ["concentration", "zone_diameter_mm"] if "zone" in db_model.model_type else (
        ["concentration"] if "classification" in db_model.model_type else ["time_h", "temperature", "ph"]
    )
    feature_names = cat_cols + num_cols

    raw_importances = estimator.feature_importances_

    # Aggregate one-hot encoded categories back to parent feature names
    parent_map = {}
    for name, imp in zip(feature_names, raw_importances):
        parent = name.split("_")[0] if "_" in name else name
        parent_map[parent] = parent_map.get(parent, 0.0) + float(imp)

    # Normalize to percentages
    total_imp = sum(parent_map.values()) or 1.0
    importance_list = [
        {"feature": k, "importance": round((v / total_imp) * 100.0, 2)}
        for k, v in parent_map.items()
    ]
    importance_list.sort(key=lambda x: x["importance"], reverse=True)

    return {
        "success": True,
        "model_name": db_model.name,
        "importances": importance_list,
        "notice": ML_NOTICE,
        "explainability_notice": EXPLAINABILITY_NOTICE
    }


def predict_ast(
    organism: str,
    antibiotic: str,
    antibiotic_class: str,
    concentration: float = 10.0,
    zone_diameter_mm: Optional[float] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Execute live inference on trained AST classification models."""
    variant = "classification_zone" if zone_diameter_mm is not None else "classification_no_zone"
    db_model = MLModel.query.filter_by(model_type=variant, algorithm="Random Forest").first()

    if not db_model or not is_safe_model_path(db_model.file_path):
        return {
            "success": False,
            "error": f"Model for variant '{variant}' has not been trained yet. Train models in the ML Lab."
        }

    pipeline = joblib.load(db_model.file_path)

    row = {
        "organism": organism,
        "antibiotic": antibiotic,
        "antibiotic_class": antibiotic_class,
        "concentration": float(concentration)
    }
    if zone_diameter_mm is not None:
        row["zone_diameter_mm"] = float(zone_diameter_mm)

    input_df = pd.DataFrame([row])
    prediction = pipeline.predict(input_df)[0]
    probabilities = pipeline.predict_proba(input_df)[0]
    prob_dict = {cls: round(float(prob) * 100.0, 1) for cls, prob in zip(pipeline.classes_, probabilities)}

    # Log to ml_predictions
    pred_record = MLPrediction(
        user_id=user_id,
        model_id=db_model.id,
        model_name=db_model.name,
        input_json=json.dumps(row),
        prediction=str(prediction),
        probability_json=json.dumps(prob_dict)
    )
    db.session.add(pred_record)
    db.session.commit()

    return {
        "success": True,
        "prediction": str(prediction),
        "probabilities": prob_dict,
        "model_used": db_model.name,
        "notice": ML_NOTICE
    }
