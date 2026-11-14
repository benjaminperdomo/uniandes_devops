from sqlalchemy.exc import OperationalError

from app.extensions import db


def test_unexpected_error_returns_json_500_and_is_logged(client, auth_headers, monkeypatch, caplog):
    def database_down(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("connection refused"))

    monkeypatch.setattr(db.session, "execute", database_down)

    response = client.get("/blacklists/user@example.com", headers=auth_headers)

    assert response.status_code == 500
    assert response.content_type == "application/json"
    assert response.get_json() == {"message": "Internal server error"}
    assert "Unhandled error in GET /blacklists/user@example.com" in caplog.text
    assert "connection refused" in caplog.text


def test_authentication_errors_keep_their_401_response(client):
    response = client.get("/blacklists/user@example.com")

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing authorization token"


def test_unknown_route_keeps_404(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404


def test_unsupported_method_keeps_405(client):
    response = client.delete("/blacklists")

    assert response.status_code == 405
