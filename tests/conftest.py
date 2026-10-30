import uuid

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import BlacklistEntry


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        token = create_access_token(identity="test-client", expires_delta=False)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def add_entry(app):
    """Insert a blacklist entry directly in the database, without going through the API."""

    def _add_entry(email, blocked_reason=None):
        with app.app_context():
            db.session.add(BlacklistEntry(email=email, app_uuid=uuid.uuid4(), blocked_reason=blocked_reason))
            db.session.commit()

    return _add_entry
