from fastapi.testclient import TestClient

from openpdm.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_foundation_endpoint_exposes_only_foundation_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/foundation")

    assert response.status_code == 200
    assert response.json()["phase"] == "Foundation"
    assert response.json()["architecture"] == "Modular Monolith"
