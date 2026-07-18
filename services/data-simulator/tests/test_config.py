import pytest
from src.config import Settings
from pydantic import ValidationError


def create_settings(**overrides):
    defaults = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "smart_city",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "password",
        "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
        "KAFKA_TOPIC": "trash_bins",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_database_url_is_built_correctly():
    settings = create_settings()

    assert (
        settings.DATABASE_URL
        == "postgresql+asyncpg://postgres:password@localhost:5432/smart_city"
    )


def test_default_simulation_values():
    settings = create_settings()

    assert settings.NUMBER_OF_BINS == 100
    assert settings.SIMULATION_INTERVAL == 5


def test_environment_overrides_defaults():
    settings = create_settings(
        NUMBER_OF_BINS=500,
        SIMULATION_INTERVAL=10,
    )

    assert settings.NUMBER_OF_BINS == 500
    assert settings.SIMULATION_INTERVAL == 10


def test_missing_required_field_raises_validation_error(monkeypatch):
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            POSTGRES_PORT=5432,
            POSTGRES_DB="smart_city",
            POSTGRES_USER="postgres",
            POSTGRES_PASSWORD="password",
            KAFKA_BOOTSTRAP_SERVERS="kafka:9092",
            KAFKA_TOPIC="trash_bins",
        )


def test_database_url_changes_when_values_change():
    settings = create_settings(
        POSTGRES_HOST="database",
        POSTGRES_DB="production",
    )

    assert (
        settings.DATABASE_URL
        == "postgresql+asyncpg://postgres:password@database:5432/production"
    )


def test_invalid_port_raises_validation_error():
    """
    Test that a non-integer POSTGRES_PORT is rejected by pydantic validation,
    since the field is typed as int.
    """
    with pytest.raises(ValidationError):
        create_settings(POSTGRES_PORT="not-a-port")
