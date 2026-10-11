import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.config import TestingConfig
from app.extensions import db


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
