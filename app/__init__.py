import click
from flask import Flask
from flask_jwt_extended import create_access_token
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config, build_database_uri
from app.extensions import db, jwt, ma
from app.resources import register_resources


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

        db.create_all()

    return app


def register_commands(app):
    @app.cli.command("generate-token")
    @click.option("--identity", default="blacklist-client", show_default=True, help="Token subject.")
    def generate_token(identity):
        """Print a non-expiring JWT signed with JWT_SECRET_KEY."""
        click.echo(create_access_token(identity=identity, expires_delta=False))
