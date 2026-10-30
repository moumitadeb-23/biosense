from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np


def sanitize_formula_injection(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Neutralize spreadsheet formula injection on CSV exports.
    
    Prepends a single quote (') to any string starting with '=', '+', '-', '@', '\t', '\r'.
    """
    sanitized_df = df.copy()
    neutralized_count = 0
    formula_prefixes = ("=", "+", "-", "@", "\t", "\r")

    for col in sanitized_df.columns:
        if sanitized_df[col].dtype == "object":
            for idx in sanitized_df.index:
                val = str(sanitized_df.at[idx, col])
                if val.startswith(formula_prefixes):
                    sanitized_df.at[idx, col] = f"'{val}"
                    neutralized_count += 1

    return sanitized_df, neutralized_count


def clean_dataframe(
    df: pd.DataFrame,
    dataset_type: str,
    drop_duplicates: bool = True,
    drop_invalid_biological: bool = True,
    impute_missing: bool = False
) -> Tuple[pd.DataFrame, List[str]]:
    """Clean the dataset according to user-selected strategies and produce an explicit audit change log.
    
    NEVER silently alter data: all deletions, imputations, or bounding clamps are logged.
    """
    cleaned_df = df.copy()
    change_log: List[str] = []

    # Normalize column names for safe access
    orig_cols = list(cleaned_df.columns)
    col_map = {c: str(c).strip().lower() for c in orig_cols}
    cleaned_df = cleaned_df.rename(columns=col_map)

    initial_count = len(cleaned_df)

    # 1. Handle Duplicates
    if drop_duplicates:
        dups = cleaned_df.duplicated()
        dup_count = int(dups.sum())
        if dup_count > 0:
            cleaned_df = cleaned_df.drop_duplicates()
            change_log.append(f"Removed {dup_count} duplicate row(s) from the dataset.")

    # 2. Handle Biological Range Violations
    if drop_invalid_biological:
        rows_to_drop = []

        if dataset_type == "growth":
            for idx, row in cleaned_df.iterrows():
                od = row.get("optical_density")
                time_h = row.get("time_h")
                ph = row.get("ph")
                temp = row.get("temperature")

                # Check OD
                try:
                    od_num = float(od)
                    if od_num < 0:
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to biologically impossible negative OD600 ({od})."))
                        continue
                    elif od_num > 5.0:
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to spectrophotometer saturation limit OD600 > 5.0 ({od})."))
                        continue
                except (ValueError, TypeError):
                    rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to non-numeric OD600 measurement ({od})."))
                    continue

                # Check Time
                try:
                    time_num = float(time_h)
                    if time_num < 0:
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to negative incubation time ({time_h}h)."))
                        continue
                except (ValueError, TypeError):
                    rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to non-numeric incubation time ({time_h})."))
                    continue

                # Check pH
                if "ph" in cleaned_df.columns and pd.notna(ph) and str(ph).strip() != "":
                    try:
                        ph_num = float(ph)
                        if ph_num < 0.0 or ph_num > 14.0:
                            rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to impossible pH outside 0–14 scale ({ph})."))
                            continue
                    except (ValueError, TypeError):
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to non-numeric pH ({ph})."))
                        continue

                # Check Temp
                if "temperature" in cleaned_df.columns and pd.notna(temp) and str(temp).strip() != "":
                    try:
                        temp_num = float(temp)
                        if temp_num < 0.0 or temp_num > 100.0:
                            rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to incubation temperature outside 0–100°C ({temp}°C)."))
                            continue
                    except (ValueError, TypeError):
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to non-numeric temperature ({temp})."))
                        continue

        elif dataset_type == "susceptibility":
            for idx, row in cleaned_df.iterrows():
                zone = row.get("zone_diameter_mm")
                cat = row.get("category")

                if "zone_diameter_mm" in cleaned_df.columns and pd.notna(zone):
                    try:
                        zone_num = float(zone)
                        if zone_num < 0 or zone_num > 60:
                            rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to zone diameter outside 0–60mm ({zone}mm)."))
                            continue
                    except (ValueError, TypeError):
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to non-numeric zone diameter ({zone})."))
                        continue

                if "category" in cleaned_df.columns and pd.notna(cat):
                    cat_str = str(cat).strip().upper()
                    if cat_str and cat_str not in ["S", "I", "R"]:
                        rows_to_drop.append((idx, f"Row {idx+2}: Dropped due to invalid category '{cat}' (must be S, I, or R)."))
                        continue

        # Drop collected invalid indices
        if rows_to_drop:
            drop_indices = [r[0] for r in rows_to_drop]
            cleaned_df = cleaned_df.drop(index=drop_indices)
            for _, msg in rows_to_drop:
                change_log.append(msg)

    # 3. Handle Missing Values
    if impute_missing:
        # Numeric columns imputed with median; categorical with mode
        for col in cleaned_df.columns:
            missing_count = int(cleaned_df[col].isna().sum())
            if missing_count > 0:
                if pd.api.types.is_numeric_dtype(cleaned_df[col]):
                    med_val = cleaned_df[col].median()
                    cleaned_df[col] = cleaned_df[col].fillna(med_val)
                    change_log.append(f"Imputed {missing_count} missing value(s) in numeric column '{col}' with column median ({round(med_val, 3)}).")
                else:
                    mode_val = cleaned_df[col].mode()
                    if not mode_val.empty:
                        fill_val = mode_val[0]
                        cleaned_df[col] = cleaned_df[col].fillna(fill_val)
                        change_log.append(f"Imputed {missing_count} missing value(s) in categorical column '{col}' with mode ('{fill_val}').")
    else:
        # If not imputing, drop remaining rows containing NaN
        before_drop = len(cleaned_df)
        cleaned_df = cleaned_df.dropna()
        dropped_missing = before_drop - len(cleaned_df)
        if dropped_missing > 0:
            change_log.append(f"Dropped {dropped_missing} row(s) containing missing / null values.")

    # 4. Neutralize spreadsheet injection on output
    cleaned_df, neutralized = sanitize_formula_injection(cleaned_df)
    if neutralized > 0:
        change_log.append(f"Neutralized {neutralized} cell(s) starting with formula characters (=, +, -, @) to prevent spreadsheet code injection.")

    final_count = len(cleaned_df)
    change_log.insert(0, f"Cleaning complete: Started with {initial_count} rows, retained {final_count} valid biological rows ({initial_count - final_count} rows removed).")

    return cleaned_df, change_log
