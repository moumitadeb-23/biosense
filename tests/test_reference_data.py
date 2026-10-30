import pytest
import pandas as pd
from scripts.generate_sample_data import (
    ORGANISMS,
    ANTIBIOTICS,
    MEDIA,
    generate_growth_data,
    generate_susceptibility_data,
)
from scripts.seed_db import seed_database
from database.models import Organism, Antibiotic, Medium, Experiment, SusceptibilityTest


def test_reference_catalogs_scientific_facts():
    """Verify that reference organisms and antibiotics contain only established microbiology facts."""
    assert len(ORGANISMS) >= 12
    for org in ORGANISMS:
        assert " " in org["scientific_name"]  # Binomial nomenclature (Genus species)
        assert org["genus"] in org["scientific_name"]
        assert org["gram_type"] in ["Gram-positive", "Gram-negative", "Fungus"]
        assert 20.0 <= org["opt_temp"] <= 45.0
        assert 5.0 <= org["opt_ph"] <= 8.5

    assert len(ANTIBIOTICS) >= 16
    for ab in ANTIBIOTICS:
        assert len(ab["name"]) > 2
        assert ab["class"] in [
            "beta-lactam", "fluoroquinolone", "aminoglycoside", "tetracycline",
            "glycopeptide", "macrolide", "amphenicol", "oxazolidinone", "lincosamide"
        ]
        assert ab["s_breakpoint"] >= ab["r_breakpoint"]


def test_growth_data_generation():
    """Verify that synthetic growth generation produces valid noisy logistic curves."""
    df = generate_growth_data(num_experiments=10)
    assert len(df) == 130  # 10 experiments * 13 time points
    assert (df["optical_density"] >= 0).all()
    assert (df["temperature"] > 0).all()
    assert ((df["ph"] >= 0) & (df["ph"] <= 14)).all()
    assert (df["data_source"] == "Synthetic – Demonstration Data").all()


def test_susceptibility_data_generation_biological_realism():
    """Verify intrinsic resistance rules in synthetic susceptibility generation."""
    df = generate_susceptibility_data(num_tests=500)
    assert len(df) == 500
    assert set(df["category"].unique()).issubset({"S", "I", "R"})
    assert (df["zone_diameter_mm"] >= 0).all()

    # Biological check: Pseudomonas aeruginosa against Ampicillin must be Resistant (R)
    pa_amp = df[(df["organism"] == "Pseudomonas aeruginosa") & (df["antibiotic"] == "Ampicillin")]
    if len(pa_amp) > 0:
        assert (pa_amp["category"] == "R").all()


def test_database_seeding(app):
    """Test full database seeding with reference data and sample experiments."""
    with app.app_context():
        seed_database(app=app, load_samples=True)

        assert Organism.query.count() >= 12
        assert Antibiotic.query.count() >= 16
        assert Medium.query.count() >= 3
        assert Experiment.query.count() > 0
        assert SusceptibilityTest.query.count() > 0
