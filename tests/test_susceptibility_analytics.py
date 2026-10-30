import pytest
from services.susceptibility_service import get_susceptibility_summary
from database.models import Organism, Antibiotic, SusceptibilityTest


def test_susceptibility_empty_database_handling(app):
    """Verify that susceptibility summary handles an empty database gracefully."""
    with app.app_context():
        summary = get_susceptibility_summary()
        assert summary["total_tests"] == 0
        assert summary["counts"]["S"] == 0
        assert summary["percentages"]["S"] == 0.0
        assert summary["resistance_rate"] == 0.0
        assert "No antibiotic susceptibility test records found" in summary["observations_summary"]


def test_susceptibility_calculation_and_dataset_wording(app):
    """Verify S/I/R calculations and strict dataset-derived non-prescriptive phrasing."""
    with app.app_context():
        # Insert test organism & antibiotics
        org = Organism(scientific_name="Klebsiella pneumoniae", common_name="K. pneumoniae", gram_type="Gram-negative")
        ab1 = Antibiotic(name="Meropenem", antibiotic_class="beta-lactam")
        ab2 = Antibiotic(name="Ampicillin", antibiotic_class="beta-lactam")
        from extensions import db
        db.session.add_all([org, ab1, ab2])
        db.session.flush()

        # Add 10 tests for Meropenem: 8 Sensitive, 2 Resistant (80% S)
        for _ in range(8):
            db.session.add(SusceptibilityTest(organism_id=org.id, antibiotic_id=ab1.id, category="S", zone_diameter_mm=26.0))
        for _ in range(2):
            db.session.add(SusceptibilityTest(organism_id=org.id, antibiotic_id=ab1.id, category="R", zone_diameter_mm=12.0))

        # Add 10 tests for Ampicillin: 1 Sensitive, 9 Resistant (10% S, 90% R)
        db.session.add(SusceptibilityTest(organism_id=org.id, antibiotic_id=ab2.id, category="S", zone_diameter_mm=19.0))
        for _ in range(9):
            db.session.add(SusceptibilityTest(organism_id=org.id, antibiotic_id=ab2.id, category="R", zone_diameter_mm=8.0))

        db.session.commit()

        # Run summary
        summary = get_susceptibility_summary(organism_id=org.id)
        assert summary["total_tests"] == 20
        assert summary["counts"]["S"] == 9
        assert summary["counts"]["R"] == 11
        assert summary["percentages"]["S"] == 45.0
        assert summary["percentages"]["R"] == 55.0

        # Antibiotic ranking check
        assert summary["antibiotic_breakdown"][0]["antibiotic"] == "Meropenem"
        assert summary["antibiotic_breakdown"][0]["s_pct"] == 80.0

        # Strict wording validation (Spec Section 12)
        summary_text = summary["observations_summary"]
        assert "Within the analyzed dataset" in summary_text
        assert "highest proportion of observations categorized as Sensitive" in summary_text
        assert "Klebsiella pneumoniae" in summary_text

        # Strictly verify no prescriptive medical claims
        lower_text = summary_text.lower()
        forbidden_words = ["prescribe", "treatment choice", "recommended therapy", "best antibiotic", "cure"]
        for word in forbidden_words:
            assert word not in lower_text


def test_susceptibility_routes_http(client, app):
    """Test AST dashboard and JSON summary API."""
    with app.app_context():
        from scripts.seed_db import seed_database
        seed_database(app=app, load_samples=False)

    resp = client.get("/susceptibility/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Antibiotic Susceptibility Testing" in html
    assert "Educational/Research Analytics" in html

    api_resp = client.get("/susceptibility/api/summary")
    assert api_resp.status_code == 200
    data = api_resp.get_json()
    assert "counts" in data
    assert "percentages" in data
