from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from flask_jwt_extended import decode_token

from app import TABLE_CREATION_LOCK_KEY, create_app, create_tables
from app.config import TestingConfig
from app.extensions import db


def test_create_app_requires_a_jwt_secret_key():
    class NoSecretConfig(TestingConfig):
        JWT_SECRET_KEY = None

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        create_app(NoSecretConfig)


def test_create_app_resolves_the_database_uri_from_the_environment(monkeypatch):
    class NoUriConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = None

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    app = create_app(NoUriConfig)

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_create_app_registers_the_expected_routes(app):
    rules = {(rule.rule, method) for rule in app.url_map.iter_rules() for method in rule.methods}

    assert ("/health", "GET") in rules
    assert ("/blacklists", "POST") in rules
    assert ("/blacklists/<string:email>", "GET") in rules


def test_create_tables_takes_an_advisory_lock_on_postgresql(app):
    connection = MagicMock()
    connection.dialect.name = "postgresql"

    @contextmanager
    def begin():
        yield connection

    engine = SimpleNamespace(begin=begin)
    with app.app_context(), patch.object(type(db), "engine", new_callable=PropertyMock, return_value=engine):
        with patch.object(db.metadata, "create_all") as create_all:
            create_tables()

    lock_call = connection.execute.call_args
    assert lock_call.args[1] == {"key": TABLE_CREATION_LOCK_KEY}
    create_all.assert_called_once_with(connection)


def test_create_tables_is_idempotent(app):
    with app.app_context():
        create_tables()
        create_tables()


def test_generate_token_command_prints_a_non_expiring_token(app):
    result = app.test_cli_runner().invoke(args=["generate-token"])

    assert result.exit_code == 0
    with app.app_context():
        claims = decode_token(result.output.strip())
    assert claims["sub"] == "blacklist-client"
    assert "exp" not in claims


def test_generate_token_command_accepts_an_identity(app):
    result = app.test_cli_runner().invoke(args=["generate-token", "--identity", "another-client"])

    assert result.exit_code == 0
    with app.app_context():
        assert decode_token(result.output.strip())["sub"] == "another-client"


def test_generated_token_is_accepted_by_the_api(app):
    token = app.test_cli_runner().invoke(args=["generate-token"]).output.strip()

    response = app.test_client().get("/blacklists/user@example.com", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
