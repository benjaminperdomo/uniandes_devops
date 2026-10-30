def test_health_returns_status_and_version(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"status": "ok", "version": "test"}


def test_health_does_not_require_token(client):
    response = client.get("/health", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 200


def test_health_rejects_unsupported_methods(client):
    response = client.post("/health")

    assert response.status_code == 405
