import pytest

from app.extensions import db
from app.models import BlacklistEntry

VALID_UUID = "6f1c2a3e-8b4d-4f5a-9c7e-1d2b3c4d5e6f"


@pytest.fixture
def payload():
    return {
        "email": "user@example.com",
        "app_uuid": VALID_UUID,
        "blocked_reason": "Spam reports",
    }


def test_create_blacklist_entry(client, app, auth_headers, payload):
    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.content_type == "application/json"
    assert response.get_json()["message"] == "Email added to the blacklist"

    with app.app_context():
        entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
        assert entry.email == "user@example.com"
        assert str(entry.app_uuid) == VALID_UUID
        assert entry.blocked_reason == "Spam reports"
        assert entry.request_ip == "127.0.0.1"
        assert entry.created_at is not None


def test_create_stores_client_ip_behind_proxies(client, app, auth_headers, payload):
    # Load balancer + nginx: the real client is the second-to-last X-Forwarded-For hop.
    headers = {**auth_headers, "X-Forwarded-For": "203.0.113.7, 10.0.0.5"}

    response = client.post("/blacklists", json=payload, headers=headers)

    assert response.status_code == 201
    with app.app_context():
        entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
        assert entry.request_ip == "203.0.113.7"


def test_create_without_blocked_reason(client, auth_headers, payload):
    del payload["blocked_reason"]

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201


def test_create_duplicate_email_returns_409(client, auth_headers, payload):
    client.post("/blacklists", json=payload, headers=auth_headers)

    response = client.post("/blacklists", json={**payload, "email": "USER@example.com"}, headers=auth_headers)

    assert response.status_code == 409


def test_create_without_token_returns_401(client, payload):
    response = client.post("/blacklists", json=payload)

    assert response.status_code == 401


def test_create_with_invalid_token_returns_401(client, payload):
    response = client.post("/blacklists", json=payload, headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401


def test_create_with_invalid_uuid_returns_400(client, auth_headers, payload):
    payload["app_uuid"] = "not-a-uuid"

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "app_uuid" in response.get_json()["errors"]


def test_create_with_invalid_email_returns_400(client, auth_headers, payload):
    payload["email"] = "not-an-email"

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "email" in response.get_json()["errors"]


def test_create_with_too_long_reason_returns_400(client, auth_headers, payload):
    payload["blocked_reason"] = "x" * 256

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "blocked_reason" in response.get_json()["errors"]


def test_create_without_required_fields_returns_400(client, auth_headers):
    response = client.post("/blacklists", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"email", "app_uuid"}
