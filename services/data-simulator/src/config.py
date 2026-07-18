from pydantic import computed_field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC: str

    NUMBER_OF_BINS: int = 100
    SIMULATION_INTERVAL: int = 5

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )


# settings = Settings() <- this will crash when they are ran by test cases


@lru_cache
def get_settings() -> Settings:
    return Settings()
