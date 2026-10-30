import pytest
from database.models import Experiment, GrowthMeasurement, SusceptibilityTest, Organism


def test_dashboard_empty_state_rendering(client):
    """Test that the dashboard gracefully handles an empty database with a seeding prompt."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Microbial &amp; AST Analytics Dashboard" in html or "Microbial & AST Analytics Dashboard" in html
    assert "No Active Research Records Detected" in html
    assert "Seed Demonstration Sample Data" in html


def test_dashboard_api_seed_demo_and_kpis(client, app):
    """Test seeding demo data from dashboard API and checking KPI aggregations."""
    # Seed via API
    seed_resp = client.post("/dashboard/api/seed-demo")
    assert seed_resp.status_code == 200
    assert seed_resp.get_json()["success"] is True

    # Re-fetch dashboard
    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # KPIs must now be non-zero
    with app.app_context():
        assert Experiment.query.count() > 0
        assert Organism.query.count() >= 12
        assert SusceptibilityTest.query.count() > 0


def test_dashboard_api_charts(client, app):
    """Test that /dashboard/api/charts returns valid payload structures for all 8 Plotly charts."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=True)

    resp = client.get("/dashboard/api/charts")
    assert resp.status_code == 200
    data = resp.get_json()

    # Verify all 8 chart payload keys exist
    assert "growth_trajectories" in data
    assert "ast_donut" in data
    assert "temp_od_scatter" in data
    assert "ab_resistance" in data
    assert "ph_dist" in data
    assert "media_yield" in data
    assert "gram_comparison" in data
    assert "timeline" in data

    # Verify contents
    assert len(data["ast_donut"]["values"]) == 3
    assert len(data["gram_comparison"]["categories"]) == 2
