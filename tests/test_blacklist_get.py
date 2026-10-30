def test_get_blacklisted_email(client, auth_headers, add_entry):
    add_entry("user@example.com", "Spam reports")

    response = client.get("/blacklists/user@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"is_blacklisted": True, "blocked_reason": "Spam reports"}


def test_get_blacklisted_email_without_reason(client, auth_headers, add_entry):
    add_entry("user@example.com")

    response = client.get("/blacklists/user@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {"is_blacklisted": True, "blocked_reason": None}


def test_get_email_not_in_blacklist(client, auth_headers):
    response = client.get("/blacklists/unknown@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {"is_blacklisted": False, "blocked_reason": None}


def test_get_only_matches_the_exact_email(client, auth_headers, add_entry):
    add_entry("user@example.com")

    response = client.get("/blacklists/other@example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["is_blacklisted"] is False


def test_get_is_case_insensitive(client, auth_headers, add_entry):
    add_entry("user@example.com")

    response = client.get("/blacklists/USER@Example.com", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {"is_blacklisted": True, "blocked_reason": None}


def test_get_ignores_surrounding_whitespace(client, auth_headers, add_entry):
    add_entry("user@example.com")

    response = client.get("/blacklists/%20user@example.com%20", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["is_blacklisted"] is True


def test_get_after_create_through_the_api(client, auth_headers):
    client.post(
        "/blacklists",
        json={"email": "user@example.com", "app_uuid": "6f1c2a3e-8b4d-4f5a-9c7e-1d2b3c4d5e6f"},
        headers=auth_headers,
    )

    response = client.get("/blacklists/user@example.com", headers=auth_headers)

    assert response.get_json()["is_blacklisted"] is True


def test_get_without_token_returns_401(client):
    response = client.get("/blacklists/user@example.com")

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing authorization token"


def test_get_with_invalid_token_returns_401(client):
    response = client.get("/blacklists/user@example.com", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid authorization token"


def test_get_with_wrong_authorization_scheme_returns_401(client, auth_headers):
    token = auth_headers["Authorization"].removeprefix("Bearer ")

    response = client.get("/blacklists/user@example.com", headers={"Authorization": f"Token {token}"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing authorization token"
