import math
import pytest
import numpy as np
from services.growth_service import (
    logistic_function,
    fit_logistic_growth_curve,
    simulate_logistic_growth,
)


def test_logistic_function_analytical():
    """Verify analytical mathematical properties of the Verhulst logistic equation."""
    N0 = 0.05
    K = 2.0
    r = 0.5

    # At t = 0, N(0) must equal N0
    val_0 = float(logistic_function(np.array([0.0]), N0, K, r)[0])
    assert abs(val_0 - N0) < 1e-6

    # At large t (e.g. t = 100), N(t) must approach K
    val_inf = float(logistic_function(np.array([100.0]), N0, K, r)[0])
    assert abs(val_inf - K) < 1e-4

    # At inflection point t_inf = ln((K - N0)/N0) / r, N(t) = K / 2
    t_inf = math.log((K - N0) / N0) / r
    val_inflection = float(logistic_function(np.array([t_inf]), N0, K, r)[0])
    assert abs(val_inflection - (K / 2.0)) < 1e-4


def test_fit_logistic_growth_curve_accuracy():
    """Verify that curve fitting accurately extracts kinetics metrics from time-series."""
    # Generate perfect logistic series with known parameters
    known_N0 = 0.04
    known_K = 1.80
    known_r = 0.50

    times = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
    ods = [float(logistic_function(np.array([t]), known_N0, known_K, known_r)[0]) for t in times]

    res = fit_logistic_growth_curve(times, ods)
    assert res["success"] is True
    assert abs(res["initial_od"] - known_N0) < 0.01
    assert abs(res["carrying_capacity_K"] - known_K) < 0.1
    assert res["r_squared"] > 0.98

    # Doubling time verification: td = ln(2) / mu_max
    expected_td = math.log(2.0) / res["mu_max"]
    assert abs(res["doubling_time_h"] - expected_td) < 0.1

    # Verify phase segmentation structure
    phases = res["phase_segmentation"]
    assert "lag_phase" in phases
    assert "log_phase" in phases
    assert "stationary_phase" in phases
    assert phases["lag_phase"]["start_h"] <= phases["lag_phase"]["end_h"]
    assert phases["log_phase"]["start_h"] <= phases["log_phase"]["end_h"]


def test_simulate_logistic_growth_validation():
    """Verify that simulation strictly rejects non-physical biological parameters."""
    # N0 <= 0 rejected
    with pytest.raises(ValueError, match="Initial population"):
        simulate_logistic_growth(N0=-0.05, K=1.8, r=0.5)

    # K <= N0 rejected
    with pytest.raises(ValueError, match="Carrying capacity"):
        simulate_logistic_growth(N0=1.0, K=0.5, r=0.5)

    # r <= 0 rejected
    with pytest.raises(ValueError, match="Intrinsic growth rate"):
        simulate_logistic_growth(N0=0.05, K=1.8, r=-0.2)

    # Valid simulation produces expected output
    sim = simulate_logistic_growth(N0=0.05, K=1.8, r=0.45, t_max=24.0)
    assert sim["success"] is True
    assert len(sim["curve"]) == 100
    assert "Mathematical simulation, not a laboratory prediction" in sim["notice"]


def test_growth_routes_http(client):
    """Test HTTP endpoints for growth viewer, simulator, and simulation API."""
    # Growth viewer
    resp1 = client.get("/growth/")
    assert resp1.status_code == 200
    assert "Microbial Growth Kinetics" in resp1.data.decode("utf-8")

    # Simulator page
    resp2 = client.get("/growth/simulator")
    assert resp2.status_code == 200
    assert "Verhulst Logistic Population Simulator" in resp2.data.decode("utf-8")

    # Simulation API
    resp3 = client.post("/growth/api/simulate", json={
        "N0": 0.05,
        "K": 1.80,
        "r": 0.45,
        "t_max": 24.0
    })
    assert resp3.status_code == 200
    data = resp3.get_json()
    assert data["success"] is True
    assert data["doubling_time_h"] > 0
    assert len(data["curve"]) == 100
