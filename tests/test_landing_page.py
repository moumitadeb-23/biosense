def test_landing_page_structure(client):
    """Test that the biotech SaaS landing page renders all required spec sections."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Brand and Tagline
    assert "BioSense" in html
    assert "Turning Biological Data into" in html
    assert "Intelligent Insights" in html

    # Spec Sections
    assert "Next-Gen Microbial Informatics &amp; AST Analytics" in html or "Next-Gen Microbial Informatics & AST Analytics" in html
    assert "GROWTH KINETICS MODEL" in html
    assert "Lag Phase" in html
    assert "Log (μ_max)" in html or "Log" in html
    assert "Stationary (K)" in html or "Stationary" in html

    # Workflow Steps
    assert "Ingestion &amp; Validation" in html or "Ingestion & Validation" in html
    assert "Growth Kinetics" in html
    assert "Susceptibility Profiling" in html
    assert "ML Lab &amp; PDF Reports" in html or "ML Lab & PDF Reports" in html

    # Features Grid
    assert "Kinetics Modeling &amp; Doubling Time" in html or "Kinetics Modeling & Doubling Time" in html
    assert "Standardized AST Interpretation" in html
    assert "Dual-Variant Machine Learning Lab" in html
    assert "Statistical Anomaly Screening" in html

    # Theme Toggle
    assert 'id="themeToggleBtn"' in html
    assert 'id="themeIcon"' in html

    # Clinical & Academic Disclaimer
    assert "Educational/Research Analytics — Not for Clinical Diagnosis or Treatment Decisions." in html

    # Developer & Engineering Credits
    assert "Developer &amp; Academic Engineering Credits" in html or "Developer & Academic Engineering Credits" in html
    assert "Major Project Capstone" in html
