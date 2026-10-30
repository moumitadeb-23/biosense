import json
import pytest


def test_knowledge_hub_page_renders(client):
    """Test that the Knowledge Hub & Viva Voce guide renders successfully."""
    response = client.get("/learn/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Key Educational Sections
    assert "Knowledge Hub" in html
    assert "Microbial Growth Kinetics &amp; OD600" in html or "Microbial Growth Kinetics & OD600" in html
    assert "Verhulst Logistic Differential Model" in html
    assert "Target Leakage (Variant A vs. Variant B)" in html or "Target Leakage" in html
    assert "EUCAST Breakpoints" in html or "EUCAST" in html
    assert "Verhulst Step-by-Step Arithmetic Sandbox" in html
    assert "Curated Major Project Viva Voce Examination Bank" in html
    assert "Interactive Viva Practice Quiz" in html
    assert "Biological &amp; Data Science Glossary" in html or "Biological & Data Science Glossary" in html


def test_viva_qa_api_endpoint(client):
    """Test the Viva Voce JSON API with domain and keyword filtering."""
    # 1. Fetch all questions
    res = client.get("/learn/api/viva-qa")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["count"] >= 20
    assert len(data["questions"]) >= 20

    # 2. Filter by domain
    domain_res = client.get("/learn/api/viva-qa?domain=Software Architecture")
    assert domain_res.status_code == 200
    domain_data = json.loads(domain_res.data)
    assert domain_data["count"] > 0
    assert all(q["domain"] == "Software Architecture" for q in domain_data["questions"])

    # 3. Filter by search keyword
    search_res = client.get("/learn/api/viva-qa?q=leakage")
    assert search_res.status_code == 200
    search_data = json.loads(search_res.data)
    assert search_data["count"] > 0
    assert any("leakage" in q["question"].lower() or "leakage" in q["answer"].lower() for q in search_data["questions"])


def test_quiz_api_endpoint(client):
    """Test the self-test quiz questions API."""
    res = client.get("/learn/api/quiz")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert "questions" in data
    assert len(data["questions"]) == 10

    # Check question schema
    first_q = data["questions"][0]
    assert "id" in first_q
    assert "question" in first_q
    assert "options" in first_q
    assert len(first_q["options"]) == 4
    assert "answer" in first_q
    assert isinstance(first_q["answer"], int)
    assert "explanation" in first_q


def test_download_handbook_pdf(client):
    """Test that the master documentation and viva handbook PDF can be downloaded."""
    res = client.get("/learn/download-handbook")
    assert res.status_code == 200
    assert "application/pdf" in res.headers["Content-Type"]
    assert "BioSense_Master_Project_Documentation_and_Viva_Defense_Handbook.pdf" in res.headers.get("Content-Disposition", "")
    assert len(res.data) > 50000  # Multi-page comprehensive handbook

