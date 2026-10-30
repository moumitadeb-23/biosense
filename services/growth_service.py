import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from scipy.optimize import curve_fit


def logistic_function(t: np.ndarray, N0: float, K: float, r: float) -> np.ndarray:
    """Verhulst Logistic Growth Equation: N(t) = K / (1 + ((K - N0)/N0) * exp(-r * t))."""
    return K / (1.0 + ((K - N0) / N0) * np.exp(-r * t))


def fit_logistic_growth_curve(
    time_series: List[float],
    od_series: List[float]
) -> Dict[str, Any]:
    """Fit time vs OD600 measurements to the logistic model and compute kinetics metrics.
    
    Returns initial OD, max OD, mean OD, mu_max, doubling time, time to peak, and phase boundaries.
    """
    if len(time_series) < 3:
        return {
            "success": False,
            "error": "Insufficient data points (minimum 3 required for kinetic fitting)."
        }

    t = np.asarray(time_series, dtype=float)
    y = np.asarray(od_series, dtype=float)

    # Sort in ascending time order
    order = np.argsort(t)
    t, y = t[order], y[order]

    initial_od = float(y[0])
    max_od = float(np.max(y))
    min_od = float(np.min(y))
    mean_od = float(np.mean(y))
    time_to_max = float(t[np.argmax(y)])

    # Initial parameter guesses: N0 = initial OD, K = max OD * 1.05, r = 0.5
    p0 = [max(0.005, initial_od), max(initial_od * 1.1, max_od * 1.02), 0.4]
    bounds = ([1e-4, initial_od, 1e-4], [5.0, 10.0, 5.0])

    fitted_success = True
    try:
        popt, _ = curve_fit(logistic_function, t, y, p0=p0, bounds=bounds, maxfev=10000)
        fit_N0, fit_K, fit_r = float(popt[0]), float(popt[1]), float(popt[2])
        y_pred = logistic_function(t, fit_N0, fit_K, fit_r)

        # Coefficient of determination R^2
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = float(1.0 - (ss_res / (ss_tot + 1e-9)))
    except Exception:
        fitted_success = False
        fit_N0 = initial_od
        fit_K = max_od
        fit_r = 0.35
        r_squared = 0.0

    # Exponential log-linear slope estimation for mu_max
    # Compute derivative of ln(y) to find maximal growth rate region
    mu_max = fit_r
    if len(y) >= 4:
        valid_log = y > 0
        if np.sum(valid_log) >= 4:
            t_log = t[valid_log]
            ln_y = np.log(y[valid_log])
            # Sliding 3-point slope
            slopes = []
            for i in range(len(t_log) - 2):
                dt = t_log[i + 2] - t_log[i]
                if dt > 0:
                    slope = (ln_y[i + 2] - ln_y[i]) / dt
                    slopes.append(slope)
            if slopes:
                max_slope = max(slopes)
                if max_slope > 0:
                    mu_max = float(max_slope)

    # Approximate Doubling Time: t_d = ln(2) / mu_max
    doubling_time_h = float(math.log(2.0) / mu_max) if mu_max > 0 else 0.0

    # Heuristic Educational Phase Segmentation
    # Lag phase: where OD change < 8% of total delta
    od_range = max_od - initial_od
    lag_threshold = initial_od + (0.08 * od_range)
    lag_indices = np.where(y <= lag_threshold)[0]
    lag_end_t = float(t[lag_indices[-1]]) if len(lag_indices) > 0 else float(t[0])

    # Stationary phase: where OD >= 90% of max OD
    stationary_threshold = max_od - (0.10 * od_range)
    stat_indices = np.where(y >= stationary_threshold)[0]
    stationary_start_t = float(t[stat_indices[0]]) if len(stat_indices) > 0 else float(t[-1])

    # Ensure logical order: t[0] <= lag_end <= stationary_start <= t[-1]
    if lag_end_t >= stationary_start_t:
        lag_end_t = float(t[0] + (t[-1] - t[0]) * 0.2)
        stationary_start_t = float(t[0] + (t[-1] - t[0]) * 0.6)

    # Generate smooth predicted curve points for Plotly rendering
    t_smooth = np.linspace(float(t[0]), float(t[-1]), 100)
    y_smooth = logistic_function(t_smooth, fit_N0, fit_K, fit_r)

    return {
        "success": True,
        "fitted_model": "Verhulst Logistic Equation",
        "initial_od": round(initial_od, 4),
        "max_od": round(max_od, 4),
        "min_od": round(min_od, 4),
        "mean_od": round(mean_od, 4),
        "time_to_max_h": round(time_to_max, 2),
        "mu_max": round(mu_max, 4),
        "doubling_time_h": round(doubling_time_h, 2),
        "carrying_capacity_K": round(fit_K, 4),
        "r_squared": round(max(0.0, r_squared), 4),
        "phase_segmentation": {
            "lag_phase": {"start_h": float(t[0]), "end_h": round(lag_end_t, 2)},
            "log_phase": {"start_h": round(lag_end_t, 2), "end_h": round(stationary_start_t, 2)},
            "stationary_phase": {"start_h": round(stationary_start_t, 2), "end_h": float(t[-1])}
        },
        "points": [{"t": round(float(ti), 2), "od": round(float(yi), 4)} for ti, yi in zip(t, y)],
        "smooth_curve": [{"t": round(float(ti), 2), "od": round(float(yi), 4)} for ti, yi in zip(t_smooth, y_smooth)]
    }


def simulate_logistic_growth(
    N0: float,
    K: float,
    r: float,
    t_max: float = 24.0,
    num_points: int = 100
) -> Dict[str, Any]:
    """Simulate theoretical logistic population kinetics with input validation."""
    # Strict biological validation
    if N0 <= 0:
        raise ValueError("Initial population (N0) must be strictly greater than 0.")
    if K <= N0:
        raise ValueError("Carrying capacity (K) must be strictly greater than initial population (N0).")
    if r <= 0:
        raise ValueError("Intrinsic growth rate (r) must be positive.")
    if t_max <= 0:
        raise ValueError("Simulation duration (t_max) must be positive.")

    t = np.linspace(0.0, float(t_max), num_points)
    y = logistic_function(t, N0, K, r)

    doubling_time_h = math.log(2.0) / r
    # Inflection point: t_inflection = ln((K - N0)/N0) / r
    t_inflection = math.log((K - N0) / N0) / r if K > N0 else 0.0

    return {
        "success": True,
        "N0": N0,
        "K": K,
        "r": r,
        "t_max": t_max,
        "doubling_time_h": round(doubling_time_h, 2),
        "inflection_time_h": round(max(0.0, t_inflection), 2),
        "max_growth_rate_at_inflection": round(r * K / 4.0, 4),
        "curve": [{"t": round(float(ti), 2), "od": round(float(yi), 4)} for ti, yi in zip(t, y)],
        "notice": "Mathematical simulation, not a laboratory prediction. This computational model demonstrates theoretical Verhulst population dynamics under ideal closed-system assumptions."
    }
