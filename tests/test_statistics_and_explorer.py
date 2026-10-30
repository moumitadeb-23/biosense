import pytest
from services.statistics_service import (
    compute_descriptive_statistics,
    run_welch_ttest,
    run_one_way_anova,
    get_organism_bio_explorer_profile,
)
from database.models import Organism, Medium, Experiment, GrowthMeasurement, SusceptibilityTest


def test_welch_ttest_analytical():
    """Verify Welch's t-test calculation against hand-verifiable statistics."""
    # Group A: [10, 12, 14], Mean = 12, Var = 4
    # Group B: [20, 22, 24], Mean = 22, Var = 4
    # Diff = -10, highly significant
    group_a = [10.0, 12.0, 14.0]
    group_b = [20.0, 22.0, 24.0]

    result = run_welch_ttest(group_a, group_b, label_a="A", label_b="B")
    assert result["success"] is True
    assert result["mean_a"] == 12.0
    assert result["mean_b"] == 22.0
    assert result["mean_difference"] == -10.0
    assert result["t_statistic"] < -5.0
    assert result["p_value"] < 0.01
    assert result["is_significant"] is True
    assert "statistically significant" in result["interpretation"]
    assert len(result["assumptions"]) == 4


def test_one_way_anova_analytical():
    """Verify One-Way ANOVA across multiple groups."""
    groups = {
        "Medium A": [1.0, 1.2, 1.1],
        "Medium B": [2.0, 2.1, 1.9],
        "Medium C": [3.0, 3.1, 2.9]
    }
    result = run_one_way_anova(groups)
    assert result["success"] is True
    assert result["f_statistic"] > 50.0  # Clear separation between groups
    assert result["p_value"] < 0.001
    assert result["is_significant"] is True
    assert len(result["groups"]) == 3


def test_statistics_and_bio_explorer_database(app):
    """Verify statistical queries and Bio Explorer profile generation on database."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)

        stats_summary = compute_descriptive_statistics()
        assert stats_summary["has_data"] is True
        assert "optical_density" in stats_summary["variables"]
        assert stats_summary["variables"]["optical_density"]["count"] > 100
        assert stats_summary["correlation_matrix"]["matrix"] != []

        # Test Bio Explorer Profile
        org = Organism.query.first()
        profile = get_organism_bio_explorer_profile(org.id)
        assert profile is not None
        assert profile["scientific_name"] == org.scientific_name
        assert profile["experimental_summary"]["experiments_count"] > 0
        assert profile["ast_summary"]["total_ast_tests"] > 0


def test_statistics_routes_http(client, app):
    """Test statistics and Bio Explorer HTTP endpoints."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=False)

    # Statistics page
    r1 = client.get("/statistics/")
    assert r1.status_code == 200
    assert "Biostatistical Analytics" in r1.data.decode("utf-8")

    # Explorer page
    r2 = client.get("/statistics/explorer")
    assert r2.status_code == 200
    assert "Bio Explorer" in r2.data.decode("utf-8")

    # Hypothesis test API
    r3 = client.post("/statistics/api/hypothesis-test", json={"test_type": "ttest"})
    assert r3.status_code == 200
