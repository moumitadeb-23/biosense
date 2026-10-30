from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from extensions import db
from database.models import GrowthMeasurement, Experiment


def detect_growth_anomalies(
    contamination: float = 0.05
) -> Dict[str, Any]:
    """Screen optical density growth observations for statistical outliers using IQR, Z-Score, and Isolation Forest.
    
    Notice: An anomaly indicates a statistical outlier relative to dataset distribution,
    not necessarily laboratory error or contaminated culture.
    """
    rows = (
        db.session.query(
            GrowthMeasurement.id,
            GrowthMeasurement.time_h,
            GrowthMeasurement.optical_density,
            Experiment.temperature,
            Experiment.ph
        )
        .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
        .limit(1000)
        .all()
    )

    if len(rows) < 15:
        return {
            "success": False,
            "error": "Insufficient growth records (minimum 15 required for anomaly screening).",
            "total_screened": len(rows),
            "anomalies": []
        }

    df = pd.DataFrame(rows, columns=["id", "time_h", "od", "temp", "ph"])

    # 1. IQR Method on Optical Density
    q25 = float(df["od"].quantile(0.25))
    q75 = float(df["od"].quantile(0.75))
    iqr = q75 - q25
    iqr_lower = q25 - 1.5 * iqr
    iqr_upper = q75 + 1.5 * iqr
    df["iqr_anomaly"] = (df["od"] < iqr_lower) | (df["od"] > iqr_upper)

    # 2. Z-Score Method (|Z| > 2.8)
    mean_od = float(df["od"].mean())
    std_od = float(df["od"].std())
    if std_od > 0:
        df["z_score"] = ((df["od"] - mean_od) / std_od).round(2)
        df["z_anomaly"] = df["z_score"].abs() > 2.8
    else:
        df["z_score"] = 0.0
        df["z_anomaly"] = False

    # 3. Isolation Forest Ensemble
    features = df[["time_h", "od", "temp", "ph"]].fillna(df.median())
    iso = IsolationForest(contamination=contamination, random_state=42)
    df["iso_anomaly"] = iso.fit_predict(features) == -1

    # Combined anomaly flag (flagged by at least 1 method)
    df["is_anomaly"] = df["iqr_anomaly"] | df["z_anomaly"] | df["iso_anomaly"]
    anomaly_subset = df[df["is_anomaly"]]

    records = []
    for _, r in anomaly_subset.iterrows():
        methods = []
        if r["iqr_anomaly"]: methods.append("IQR Outlier")
        if r["z_anomaly"]: methods.append(f"Z-Score ({r['z_score']})")
        if r["iso_anomaly"]: methods.append("Isolation Forest")

        records.append({
            "measurement_id": int(r["id"]),
            "time_h": float(r["time_h"]),
            "optical_density": float(r["od"]),
            "temperature": float(r["temp"]),
            "ph": float(r["ph"]),
            "detected_by": methods
        })

    return {
        "success": True,
        "total_screened": len(df),
        "total_anomalies": len(anomaly_subset),
        "anomaly_rate_pct": round((len(anomaly_subset) / len(df)) * 100.0, 1),
        "iqr_bounds": {"lower": round(iqr_lower, 3), "upper": round(iqr_upper, 3)},
        "z_score_threshold": 2.8,
        "anomalies": records,
        "notice": "An anomaly indicates a statistical outlier relative to dataset distribution, not necessarily laboratory error."
    }
