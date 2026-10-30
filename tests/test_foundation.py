import json


def test_app_is_testing(app):
    """Test that the application starts with testing configuration."""
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_health_check_endpoint(client):
    """Test that the /health endpoint responds with 200 and valid JSON status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert "BioSense" in data["service"]
    assert data["version"] == "1.0.0"


def test_index_landing_renders(client):
    """Test that the landing page renders successfully with platform tagline."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "BioSense" in html
    assert "Turning Biological Data into" in html
