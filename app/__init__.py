import click
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config, build_database_uri
from app.extensions import db, jwt, ma
from app.resources import register_resources

# Arbitrary key shared by every process that creates the tables.
TABLE_CREATION_LOCK_KEY = 7301202601


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_FIX_X_FOR"])

    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)

    register_resources(app)
    register_commands(app)

    with app.app_context():
        from app import models  # noqa: F401  (registers the models before creating tables)

        create_tables()

    return app


def create_tables():
    """Create missing tables. On PostgreSQL an advisory lock serializes the gunicorn workers and
    instances that start at the same time, so they do not race creating the same table."""
    with db.engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": TABLE_CREATION_LOCK_KEY})
        db.metadata.create_all(connection)


def register_commands(app):
    @app.cli.command("generate-token")
    @click.option("--identity", default="blacklist-client", show_default=True, help="Token subject.")
    def generate_token(identity):
        """Print a non-expiring JWT signed with JWT_SECRET_KEY."""
        click.echo(create_access_token(identity=identity, expires_delta=False))
