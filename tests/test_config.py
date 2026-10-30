import pytest

from app import config

DATABASE_VARIABLES = ("DATABASE_URL", "RDS_HOSTNAME", "RDS_PORT", "RDS_DB_NAME", "RDS_USERNAME", "RDS_PASSWORD")


@pytest.fixture
def clean_database_env(monkeypatch):
    for name in DATABASE_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_read_app_version_prefers_the_environment_variable(monkeypatch, tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n")
    monkeypatch.setattr(config, "VERSION_FILE", version_file)
    monkeypatch.setenv("APP_VERSION", "9.9.9")

    assert config.read_app_version() == "9.9.9"


def test_read_app_version_reads_the_version_file(monkeypatch, tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n")
    monkeypatch.setattr(config, "VERSION_FILE", version_file)
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert config.read_app_version() == "1.2.3"


def test_read_app_version_defaults_to_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VERSION_FILE", tmp_path / "missing")
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert config.read_app_version() == "unknown"


def test_build_database_uri_uses_database_url(monkeypatch, clean_database_env):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.example.com:5432/blacklist")

    assert config.build_database_uri() == "postgresql://user:secret@db.example.com:5432/blacklist"


def test_build_database_uri_normalizes_the_postgres_scheme(monkeypatch, clean_database_env):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.example.com/blacklist")

    assert config.build_database_uri().startswith("postgresql://user:secret@db.example.com")


def test_build_database_uri_uses_rds_variables(monkeypatch, clean_database_env):
    monkeypatch.setenv("RDS_HOSTNAME", "db.example.com")
    monkeypatch.setenv("RDS_PORT", "5433")
    monkeypatch.setenv("RDS_DB_NAME", "blacklist")
    monkeypatch.setenv("RDS_USERNAME", "admin")
    monkeypatch.setenv("RDS_PASSWORD", "p@ss/word")

    uri = config.build_database_uri()

    assert uri.startswith("postgresql+psycopg://admin:")
    assert "@db.example.com:5433/blacklist" in uri


def test_build_database_uri_prefers_database_url_over_rds(monkeypatch, clean_database_env):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@primary.example.com/blacklist")
    monkeypatch.setenv("RDS_HOSTNAME", "rds.example.com")

    assert "primary.example.com" in config.build_database_uri()


def test_build_database_uri_requires_configuration(clean_database_env):
    with pytest.raises(RuntimeError, match="Database is not configured"):
        config.build_database_uri()
