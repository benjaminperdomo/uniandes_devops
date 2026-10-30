import pytest
from sqlalchemy.exc import IntegrityError

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


def stored_entries(app):
    with app.app_context():
        return db.session.execute(db.select(BlacklistEntry)).scalars().all()


def test_create_blacklist_entry(client, app, auth_headers, payload):
    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.content_type == "application/json"
    assert response.get_json() == {"message": "Email added to the blacklist", "email": "user@example.com"}

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


def test_create_without_blocked_reason(client, app, auth_headers, payload):
    del payload["blocked_reason"]

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert stored_entries(app)[0].blocked_reason is None


def test_create_with_null_blocked_reason(client, app, auth_headers, payload):
    payload["blocked_reason"] = None

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert stored_entries(app)[0].blocked_reason is None


def test_create_ignores_unknown_fields(client, app, auth_headers, payload):
    payload["unexpected"] = "value"

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert len(stored_entries(app)) == 1


def test_create_normalizes_email(client, app, auth_headers, payload):
    payload["email"] = "  User@Example.COM "

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.get_json()["email"] == "user@example.com"
    assert stored_entries(app)[0].email == "user@example.com"


def test_create_duplicate_email_returns_409(client, app, auth_headers, payload):
    first = client.post("/blacklists", json=payload, headers=auth_headers)

    response = client.post("/blacklists", json={**payload, "email": "USER@example.com"}, headers=auth_headers)

    assert first.status_code == 201
    assert response.status_code == 409
    assert response.get_json() == {"message": "Email is already in the blacklist"}
    assert len(stored_entries(app)) == 1


def test_create_concurrent_duplicate_returns_409(client, app, auth_headers, payload, monkeypatch):
    # Another request inserts the same email between the lookup and the commit.
    def failing_commit():
        raise IntegrityError("INSERT INTO blacklists", {}, Exception("unique constraint"))

    monkeypatch.setattr(db.session, "commit", failing_commit)

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 409
    assert response.get_json() == {"message": "Email is already in the blacklist"}
    monkeypatch.undo()
    assert stored_entries(app) == []


def test_create_without_token_returns_401(client, app, payload):
    response = client.post("/blacklists", json=payload)

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing authorization token"
    assert stored_entries(app) == []


def test_create_with_invalid_token_returns_401(client, payload):
    response = client.post("/blacklists", json=payload, headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid authorization token"


def test_create_with_tampered_token_returns_401(client, payload, auth_headers):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    header, body, signature = token.split(".")
    flipped = "A" if signature[5] != "A" else "B"
    tampered = ".".join([header, body, signature[:5] + flipped + signature[6:]])

    response = client.post("/blacklists", json=payload, headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid authorization token"


def test_create_with_wrong_authorization_scheme_returns_401(client, payload, auth_headers):
    token = auth_headers["Authorization"].removeprefix("Bearer ")

    response = client.post("/blacklists", json=payload, headers={"Authorization": f"Token {token}"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing authorization token"


def test_create_with_expired_token_returns_401(client, app, payload):
    from datetime import timedelta

    from flask_jwt_extended import create_access_token

    with app.app_context():
        expired = create_access_token(identity="test-client", expires_delta=timedelta(seconds=-1))

    response = client.post("/blacklists", json=payload, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert "expired" in str(response.get_json()).lower()


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


def test_create_with_too_long_email_returns_400(client, app, auth_headers, payload):
    payload["email"] = "a" * 64 + "@" + ".".join(["b" * 60] * 4) + ".com"
    assert len(payload["email"]) > 255

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "email" in response.get_json()["errors"]
    assert stored_entries(app) == []


def test_create_with_too_long_reason_returns_400(client, auth_headers, payload):
    payload["blocked_reason"] = "x" * 256

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "blocked_reason" in response.get_json()["errors"]


def test_create_with_reason_at_max_length_returns_201(client, auth_headers, payload):
    payload["blocked_reason"] = "x" * 255

    response = client.post("/blacklists", json=payload, headers=auth_headers)

    assert response.status_code == 201


def test_create_without_required_fields_returns_400(client, auth_headers):
    response = client.post("/blacklists", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"email", "app_uuid"}


def test_create_without_body_returns_400(client, auth_headers):
    response = client.post("/blacklists", headers=auth_headers)

    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"email", "app_uuid"}


def test_create_with_non_json_body_returns_400(client, auth_headers):
    response = client.post("/blacklists", data="email=user@example.com", headers=auth_headers)

    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"email", "app_uuid"}


def test_create_with_non_object_json_returns_400(client, auth_headers):
    response = client.post("/blacklists", json=[1, 2], headers=auth_headers)

    assert response.status_code == 400
    assert "_schema" in response.get_json()["errors"]
