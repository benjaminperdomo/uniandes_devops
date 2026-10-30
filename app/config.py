import os
from pathlib import Path

from sqlalchemy.engine import URL

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def read_app_version():
    """APP_VERSION overrides the VERSION file shipped in the deployment bundle."""
    if os.getenv("APP_VERSION"):
        return os.getenv("APP_VERSION")
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"


def build_database_uri():
    """Resolve the database URI from DATABASE_URL or the RDS_* variables injected by Elastic Beanstalk."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    if os.getenv("RDS_HOSTNAME"):
        return URL.create(
            drivername="postgresql+psycopg",
            username=os.getenv("RDS_USERNAME"),
            password=os.getenv("RDS_PASSWORD"),
            host=os.getenv("RDS_HOSTNAME"),
            port=int(os.getenv("RDS_PORT", "5432")),
            database=os.getenv("RDS_DB_NAME"),
        ).render_as_string(hide_password=False)

    raise RuntimeError("Database is not configured: set DATABASE_URL or the RDS_* variables")


class Config:
    APP_VERSION = read_app_version()
    SQLALCHEMY_DATABASE_URI = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # The static token is issued without expiration (see the generate-token command).
    JWT_ACCESS_TOKEN_EXPIRES = False
    # Let Flask-JWT-Extended errors reach their handlers instead of Flask-RESTful's generic 500.
    PROPAGATE_EXCEPTIONS = True
    # Trusted proxies in front of the app: Elastic Beanstalk load balancer + nginx.
    PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "2"))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    JWT_SECRET_KEY = "test-secret-key-with-at-least-32-chars"
    APP_VERSION = "test"
    # Fixed so the tests do not depend on the PROXY_FIX_X_FOR variable of the developer's environment.
    PROXY_FIX_X_FOR = 2
