import math
from typing import Dict, Any, List, Tuple
import pandas as pd
from database.models import Organism, Antibiotic


def detect_dataset_type(df: pd.DataFrame) -> str:
    """Determine whether the CSV contains growth curves or susceptibility observations."""
    cols = {str(c).strip().lower() for c in df.columns}
    
    if {"organism", "time_h", "optical_density"}.issubset(cols) or {"time", "od"}.issubset(cols):
        return "growth"
    elif {"organism", "antibiotic"}.issubset(cols) and ({"zone_diameter_mm", "zone"}.intersection(cols) or "category" in cols):
        return "susceptibility"
    elif "optical_density" in cols or "od" in cols:
        return "growth"
    elif "zone_diameter_mm" in cols or "antibiotic" in cols:
        return "susceptibility"
    return "unknown"


def validate_growth_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Perform rigorous schema, type, and biological range validation on growth data."""
    total_rows = len(df)
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # Standardize column names (strip whitespace and lower)
    col_map = {c: str(c).strip().lower() for c in df.columns}
    norm_df = df.rename(columns=col_map)

    # 1. Check required columns
    required_cols = ["organism", "time_h", "optical_density"]
    missing_cols = [c for c in required_cols if c not in norm_df.columns]
    if missing_cols:
        return {
            "dataset_type": "growth",
            "is_valid": False,
            "fatal_error": f"Missing mandatory columns: {', '.join(missing_cols)}",
            "total_rows": total_rows,
            "valid_rows": 0,
            "invalid_rows": total_rows,
            "duplicate_rows": 0,
            "missing_values_count": 0,
            "errors": [{"row": 0, "column": "header", "value": "N/A", "reason": f"Missing columns: {missing_cols}", "severity": "FATAL"}],
            "warnings": []
        }

    # 2. Check duplicates
    duplicate_mask = norm_df.duplicated()
    duplicate_count = int(duplicate_mask.sum())

    # 3. Missing values count
    missing_count = int(norm_df.isna().sum().sum())

    # Reference organisms lookup for validation
    valid_orgs = set()
    try:
        valid_orgs = {o.scientific_name for o in Organism.query.all()}
    except Exception:
        pass

    invalid_row_indices = set()

    # Iterate through rows and validate
    for idx, row in norm_df.iterrows():
        row_num = idx + 2  # 1-indexed accounting for CSV header
        has_error = False

        # Validate organism
        org_val = str(row.get("organism", "")).strip()
        if not org_val or pd.isna(row.get("organism")):
            errors.append({"row": row_num, "column": "organism", "value": "MISSING", "reason": "Organism name is missing.", "severity": "ERROR"})
            has_error = True
        elif valid_orgs and org_val not in valid_orgs:
            warnings.append({"row": row_num, "column": "organism", "value": org_val, "reason": "Organism is not in standard BioSense reference catalog.", "severity": "WARNING"})

        # Validate time_h
        time_val = row.get("time_h")
        try:
            time_num = float(time_val)
            if math.isnan(time_num) or time_num < 0:
                errors.append({"row": row_num, "column": "time_h", "value": str(time_val), "reason": "Time must be a non-negative number.", "severity": "ERROR"})
                has_error = True
        except (ValueError, TypeError):
            errors.append({"row": row_num, "column": "time_h", "value": str(time_val), "reason": "Time is not a valid numeric float.", "severity": "ERROR"})
            has_error = True

        # Validate optical_density (OD600)
        od_val = row.get("optical_density")
        try:
            od_num = float(od_val)
            if math.isnan(od_num):
                errors.append({"row": row_num, "column": "optical_density", "value": "NaN", "reason": "OD600 measurement is empty/NaN.", "severity": "ERROR"})
                has_error = True
            elif od_num < 0:
                errors.append({"row": row_num, "column": "optical_density", "value": str(od_val), "reason": "Negative Optical Density is biologically impossible.", "severity": "ERROR"})
                has_error = True
            elif od_num > 5.0:
                errors.append({"row": row_num, "column": "optical_density", "value": str(od_val), "reason": "OD600 > 5.0 exceeds standard spectrophotometric saturation.", "severity": "ERROR"})
                has_error = True
        except (ValueError, TypeError):
            errors.append({"row": row_num, "column": "optical_density", "value": str(od_val), "reason": "Optical Density is not a valid numeric float.", "severity": "ERROR"})
            has_error = True

        # Optional: Validate pH if present
        if "ph" in norm_df.columns:
            ph_val = row.get("ph")
            if pd.notna(ph_val) and str(ph_val).strip() != "":
                try:
                    ph_num = float(ph_val)
                    if ph_num < 0.0 or ph_num > 14.0:
                        errors.append({"row": row_num, "column": "ph", "value": str(ph_val), "reason": "pH must reside within the biological spectrum (0.0 to 14.0).", "severity": "ERROR"})
                        has_error = True
                except (ValueError, TypeError):
                    errors.append({"row": row_num, "column": "ph", "value": str(ph_val), "reason": "pH is non-numeric.", "severity": "ERROR"})
                    has_error = True

        # Optional: Validate temperature if present
        if "temperature" in norm_df.columns:
            temp_val = row.get("temperature")
            if pd.notna(temp_val) and str(temp_val).strip() != "":
                try:
                    temp_num = float(temp_val)
                    if temp_num < 0.0 or temp_num > 100.0:
                        errors.append({"row": row_num, "column": "temperature", "value": str(temp_val), "reason": "Incubation temperature must be between 0°C and 100°C.", "severity": "ERROR"})
                        has_error = True
                except (ValueError, TypeError):
                    errors.append({"row": row_num, "column": "temperature", "value": str(temp_val), "reason": "Temperature is non-numeric.", "severity": "ERROR"})
                    has_error = True

        if has_error or duplicate_mask.iloc[idx]:
            invalid_row_indices.add(idx)

    invalid_rows = len(invalid_row_indices)
    valid_rows = total_rows - invalid_rows

    return {
        "dataset_type": "growth",
        "is_valid": len(errors) == 0 and duplicate_count == 0,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_count,
        "missing_values_count": missing_count,
        "errors": errors,
        "warnings": warnings,
        "fatal_error": None
    }


def validate_susceptibility_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Perform validation on antibiotic susceptibility observations."""
    total_rows = len(df)
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    col_map = {c: str(c).strip().lower() for c in df.columns}
    norm_df = df.rename(columns=col_map)

    required_cols = ["organism", "antibiotic"]
    missing_cols = [c for c in required_cols if c not in norm_df.columns]
    if missing_cols or ("zone_diameter_mm" not in norm_df.columns and "category" not in norm_df.columns):
        missing_all = missing_cols + (["zone_diameter_mm or category"] if "zone_diameter_mm" not in norm_df.columns and "category" not in norm_df.columns else [])
        return {
            "dataset_type": "susceptibility",
            "is_valid": False,
            "fatal_error": f"Missing mandatory columns: {', '.join(missing_all)}",
            "total_rows": total_rows,
            "valid_rows": 0,
            "invalid_rows": total_rows,
            "duplicate_rows": 0,
            "missing_values_count": 0,
            "errors": [{"row": 0, "column": "header", "value": "N/A", "reason": f"Missing columns: {missing_all}", "severity": "FATAL"}],
            "warnings": []
        }

    duplicate_mask = norm_df.duplicated()
    duplicate_count = int(duplicate_mask.sum())
    missing_count = int(norm_df.isna().sum().sum())

    valid_antibiotics = set()
    try:
        valid_antibiotics = {a.name for a in Antibiotic.query.all()}
    except Exception:
        pass

    invalid_row_indices = set()

    for idx, row in norm_df.iterrows():
        row_num = idx + 2
        has_error = False

        # Organism check
        org_val = str(row.get("organism", "")).strip()
        if not org_val or pd.isna(row.get("organism")):
            errors.append({"row": row_num, "column": "organism", "value": "MISSING", "reason": "Organism name is missing.", "severity": "ERROR"})
            has_error = True

        # Antibiotic check
        ab_val = str(row.get("antibiotic", "")).strip()
        if not ab_val or pd.isna(row.get("antibiotic")):
            errors.append({"row": row_num, "column": "antibiotic", "value": "MISSING", "reason": "Antibiotic name is missing.", "severity": "ERROR"})
            has_error = True
        elif valid_antibiotics and ab_val not in valid_antibiotics:
            warnings.append({"row": row_num, "column": "antibiotic", "value": ab_val, "reason": "Antibiotic is not in BioSense reference catalog.", "severity": "WARNING"})

        # Zone diameter check if present
        if "zone_diameter_mm" in norm_df.columns:
            zone_val = row.get("zone_diameter_mm")
            if pd.notna(zone_val) and str(zone_val).strip() != "":
                try:
                    zone_num = float(zone_val)
                    if zone_num < 0.0 or zone_num > 60.0:
                        errors.append({"row": row_num, "column": "zone_diameter_mm", "value": str(zone_val), "reason": "Zone diameter must be between 0mm and 60mm.", "severity": "ERROR"})
                        has_error = True
                except (ValueError, TypeError):
                    errors.append({"row": row_num, "column": "zone_diameter_mm", "value": str(zone_val), "reason": "Zone diameter must be numeric.", "severity": "ERROR"})
                    has_error = True

        # Category check if present
        if "category" in norm_df.columns:
            cat_val = str(row.get("category", "")).strip().upper()
            if cat_val and cat_val not in ["S", "I", "R"]:
                errors.append({"row": row_num, "column": "category", "value": cat_val, "reason": "Category must strictly be 'S', 'I', or 'R'.", "severity": "ERROR"})
                has_error = True

        if has_error or duplicate_mask.iloc[idx]:
            invalid_row_indices.add(idx)

    invalid_rows = len(invalid_row_indices)
    valid_rows = total_rows - invalid_rows

    return {
        "dataset_type": "susceptibility",
        "is_valid": len(errors) == 0 and duplicate_count == 0,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_count,
        "missing_values_count": missing_count,
        "errors": errors,
        "warnings": warnings,
        "fatal_error": None
    }


def validate_csv_file(filepath: str) -> Dict[str, Any]:
    """Parse CSV and run appropriate validator."""
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {
            "dataset_type": "unknown",
            "is_valid": False,
            "fatal_error": f"Failed to parse CSV file: {str(e)}",
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicate_rows": 0,
            "missing_values_count": 0,
            "errors": [{"row": 0, "column": "file", "value": "N/A", "reason": f"Malformed CSV: {str(e)}", "severity": "FATAL"}],
            "warnings": []
        }

    dtype = detect_dataset_type(df)
    if dtype == "growth":
        return validate_growth_dataframe(df)
    elif dtype == "susceptibility":
        return validate_susceptibility_dataframe(df)
    else:
        return {
            "dataset_type": "unknown",
            "is_valid": False,
            "fatal_error": "Could not recognize dataset schema. Columns must match either Growth time-series or AST records.",
            "total_rows": len(df),
            "valid_rows": 0,
            "invalid_rows": len(df),
            "duplicate_rows": 0,
            "missing_values_count": 0,
            "errors": [{"row": 0, "column": "schema", "value": str(list(df.columns)), "reason": "Unrecognized schema", "severity": "FATAL"}],
            "warnings": []
        }
