import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import func
from extensions import db
from database.models import (
    Experiment,
    GrowthMeasurement,
    SusceptibilityTest,
    Organism,
    Antibiotic,
    Medium,
)


def compute_descriptive_statistics() -> Dict[str, Any]:
    """Calculate central tendency, dispersion, and correlations across continuous database variables."""
    # 1. Growth measurements & environmental parameters
    growth_rows = (
        db.session.query(
            GrowthMeasurement.time_h,
            GrowthMeasurement.optical_density,
            Experiment.temperature,
            Experiment.ph
        )
        .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
        .all()
    )

    # 2. AST measurements
    ast_rows = (
        db.session.query(
            SusceptibilityTest.concentration,
            SusceptibilityTest.zone_diameter_mm
        )
        .all()
    )

    if not growth_rows and not ast_rows:
        return {
            "has_data": False,
            "variables": {},
            "correlation_matrix": {"variables": [], "matrix": []}
        }

    # Build DataFrames
    gdf = pd.DataFrame(growth_rows, columns=["time_h", "optical_density", "temperature", "ph"]) if growth_rows else pd.DataFrame()
    adf = pd.DataFrame(ast_rows, columns=["concentration", "zone_diameter_mm"]) if ast_rows else pd.DataFrame()

    var_summaries = {}

    def summarize_series(series: pd.Series, name: str, unit: str = "") -> Dict[str, Any]:
        s = series.dropna().astype(float)
        if len(s) == 0:
            return {}
        q25 = float(s.quantile(0.25))
        q75 = float(s.quantile(0.75))
        return {
            "name": name,
            "unit": unit,
            "count": int(len(s)),
            "mean": round(float(s.mean()), 3),
            "median": round(float(s.median()), 3),
            "std": round(float(s.std(ddof=1)), 3) if len(s) > 1 else 0.0,
            "variance": round(float(s.var(ddof=1)), 4) if len(s) > 1 else 0.0,
            "min": round(float(s.min()), 3),
            "max": round(float(s.max()), 3),
            "q25": round(q25, 3),
            "q75": round(q75, 3),
            "iqr": round(q75 - q25, 3)
        }

    if not gdf.empty:
        var_summaries["optical_density"] = summarize_series(gdf["optical_density"], "Optical Density (OD600)", "OD")
        var_summaries["temperature"] = summarize_series(gdf["temperature"], "Incubation Temperature", "°C")
        var_summaries["ph"] = summarize_series(gdf["ph"], "Culture Acidity (pH)", "pH")
        var_summaries["time_h"] = summarize_series(gdf["time_h"], "Incubation Time", "hours")

    if not adf.empty and "zone_diameter_mm" in adf.columns and not adf["zone_diameter_mm"].dropna().empty:
        var_summaries["zone_diameter_mm"] = summarize_series(adf["zone_diameter_mm"], "Zone of Inhibition Diameter", "mm")

    # Compute correlation matrix for growth parameters
    corr_data = {"variables": [], "matrix": []}
    if not gdf.empty and len(gdf) > 5:
        numeric_cols = ["time_h", "optical_density", "temperature", "ph"]
        corr_matrix = gdf[numeric_cols].corr(method="pearson").round(3)
        corr_data = {
            "variables": ["Time (h)", "OD600", "Temp (°C)", "pH"],
            "matrix": corr_matrix.values.tolist()
        }

    return {
        "has_data": True,
        "variables": var_summaries,
        "correlation_matrix": corr_data
    }


def run_welch_ttest(group_a_values: List[float], group_b_values: List[float], label_a: str = "Group A", label_b: str = "Group B") -> Dict[str, Any]:
    """Execute Welch's two-sample unequal-variance t-test."""
    a = np.asarray(group_a_values, dtype=float)
    b = np.asarray(group_b_values, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]

    if len(a) < 2 or len(b) < 2:
        return {
            "success": False,
            "error": "Both comparison groups must contain at least 2 non-null observations."
        }

    t_stat, p_val = stats.ttest_ind(a, b, equal_var=False)

    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    diff = mean_a - mean_b

    is_significant = bool(p_val < 0.05)
    interpretation = (
        f"At significance level α = 0.05, the difference in means ({round(diff, 3)}) is "
        f"{'statistically significant (p < 0.05)' if is_significant else 'not statistically significant (p ≥ 0.05)'}."
    )

    return {
        "success": True,
        "test_name": "Welch's Two-Sample t-Test (Unequal Variances)",
        "label_a": label_a,
        "label_b": label_b,
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": round(mean_a, 3),
        "mean_b": round(mean_b, 3),
        "mean_difference": round(diff, 3),
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_val), 5),
        "is_significant": is_significant,
        "interpretation": interpretation,
        "assumptions": [
            "Continuous measurement metric.",
            "Independent random sampling between groups.",
            "Approximate normality or sufficiently large sample size (Central Limit Theorem).",
            "Does NOT assume equal variances (heteroscedasticity-robust)."
        ]
    }


def run_one_way_anova(groups: Dict[str, List[float]]) -> Dict[str, Any]:
    """Execute One-Way Analysis of Variance (ANOVA) across multiple groups."""
    clean_groups = {}
    for name, vals in groups.items():
        v = np.asarray(vals, dtype=float)
        v = v[~np.isnan(v)]
        if len(v) >= 2:
            clean_groups[name] = v

    if len(clean_groups) < 2:
        return {
            "success": False,
            "error": "ANOVA requires at least 2 distinct groups with ≥ 2 observations each."
        }

    group_arrays = list(clean_groups.values())
    f_stat, p_val = stats.f_oneway(*group_arrays)

    group_stats = []
    for name, v in clean_groups.items():
        group_stats.append({
            "group": name,
            "count": len(v),
            "mean": round(float(np.mean(v)), 3),
            "std": round(float(np.std(v, ddof=1)), 3)
        })

    is_significant = bool(p_val < 0.05)
    interpretation = (
        f"At significance level α = 0.05, the between-group variance is "
        f"{'statistically significant (p < 0.05)' if is_significant else 'not statistically significant (p ≥ 0.05)'}. "
        f"{'At least one group mean differs significantly from the others.' if is_significant else 'No significant difference detected between group means.'}"
    )

    return {
        "success": True,
        "test_name": "One-Way Analysis of Variance (ANOVA)",
        "f_statistic": round(float(f_stat), 4),
        "p_value": round(float(p_val), 5),
        "is_significant": is_significant,
        "interpretation": interpretation,
        "groups": group_stats,
        "assumptions": [
            "Observations within each group are independently and identically distributed.",
            "Normal distribution of values within each group.",
            "Homogeneity of variances across groups (homoscedasticity)."
        ]
    }


def get_organism_bio_explorer_profile(organism_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full database-backed biological and analytical profile for an organism."""
    org = Organism.query.get(organism_id)
    if not org:
        return None

    # Experiments count and conditions
    experiments = Experiment.query.filter_by(organism_id=org.id).all()
    exp_count = len(experiments)

    temps = [e.temperature for e in experiments if e.temperature]
    phs = [e.ph for e in experiments if e.ph]

    # Growth measurements
    exp_ids = [e.id for e in experiments]
    growth_count = GrowthMeasurement.query.filter(GrowthMeasurement.experiment_id.in_(exp_ids)).count() if exp_ids else 0

    # Max OD observed for this organism
    max_od_record = (
        db.session.query(func.max(GrowthMeasurement.optical_density))
        .filter(GrowthMeasurement.experiment_id.in_(exp_ids))
        .scalar()
    ) if exp_ids else 0.0

    # AST observations
    ast_tests = SusceptibilityTest.query.filter_by(organism_id=org.id).all()
    ast_count = len(ast_tests)

    s_count = sum(1 for t in ast_tests if t.category == "S")
    i_count = sum(1 for t in ast_tests if t.category == "I")
    r_count = sum(1 for t in ast_tests if t.category == "R")

    # Antibiotic Breakdown
    ab_breakdown = {}
    for t in ast_tests:
        ab_name = t.antibiotic.name
        if ab_name not in ab_breakdown:
            ab_breakdown[ab_name] = {"S": 0, "I": 0, "R": 0, "zones": []}
        ab_breakdown[ab_name][t.category] += 1
        if t.zone_diameter_mm:
            ab_breakdown[ab_name]["zones"].append(t.zone_diameter_mm)

    ab_summary_list = []
    for ab_name, d in ab_breakdown.items():
        tot = d["S"] + d["I"] + d["R"]
        avg_zone = round(float(np.mean(d["zones"])), 1) if d["zones"] else 0.0
        ab_summary_list.append({
            "antibiotic": ab_name,
            "total": tot,
            "s_pct": round((d["S"] / tot) * 100.0, 1) if tot else 0.0,
            "i_pct": round((d["I"] / tot) * 100.0, 1) if tot else 0.0,
            "r_pct": round((d["R"] / tot) * 100.0, 1) if tot else 0.0,
            "mean_zone": avg_zone
        })

    ab_summary_list.sort(key=lambda x: x["s_pct"], reverse=True)

    return {
        "id": org.id,
        "scientific_name": org.scientific_name,
        "common_name": org.common_name or org.scientific_name,
        "genus": org.genus or "Unspecified",
        "species": org.species or "Unspecified",
        "gram_type": org.gram_type or "Unspecified",
        "domain_family": org.domain_family or "Unspecified",
        "organism_type": org.organism_type or "bacterium",
        "description": org.description or "No taxonomic description recorded.",
        "experimental_summary": {
            "experiments_count": exp_count,
            "growth_points_count": growth_count,
            "max_od_observed": round(float(max_od_record), 3) if max_od_record else 0.0,
            "temp_range": f"{min(temps)}°C – {max(temps)}°C" if temps else "N/A",
            "ph_range": f"{min(phs)} – {max(phs)}" if phs else "N/A"
        },
        "ast_summary": {
            "total_ast_tests": ast_count,
            "s_pct": round((s_count / max(1, ast_count)) * 100.0, 1),
            "i_pct": round((i_count / max(1, ast_count)) * 100.0, 1),
            "r_pct": round((r_count / max(1, ast_count)) * 100.0, 1),
            "tested_antibiotics": ab_summary_list
        }
    }
