VALID_UUID = "6f1c2a3e-8b4d-4f5a-9c7e-1d2b3c4d5e6f"


def test_get_blacklisted_email(client, auth_headers):
    client.post(
        "/blacklists",
        json={"email": "user@example.com", "app_uuid": VALID_UUID, "blocked_reason": "Spam reports"},
        headers=auth_headers,
    )

    response = client.get("/blacklists/user@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"is_blacklisted": True, "blocked_reason": "Spam reports"}


def test_get_email_not_in_blacklist(client, auth_headers):
    response = client.get("/blacklists/unknown@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {"is_blacklisted": False, "blocked_reason": None}


def test_get_is_case_insensitive(client, auth_headers):
    client.post("/blacklists", json={"email": "user@example.com", "app_uuid": VALID_UUID}, headers=auth_headers)

    response = client.get("/blacklists/USER@Example.com", headers=auth_headers)

    assert response.get_json() == {"is_blacklisted": True, "blocked_reason": None}


def test_get_without_token_returns_401(client):
    response = client.get("/blacklists/user@example.com")

    assert response.status_code == 401
