import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/smart_city"
    KAFKA_BROKERS: str = "localhost:9092"
    KAFKA_TOPIC: str = "smartbin-telemetry-v1"
    TELEMETRY_INTERVAL_SEC: int = 5
    DB_POLL_INTERVAL_SEC: int = 5

    model_config = SettingsConfigDict(env_file=os.getenv("ENV_FILE", ".env.local"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()
