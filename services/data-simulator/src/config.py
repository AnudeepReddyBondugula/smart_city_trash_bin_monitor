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

    # How fast a bin fills per tick, as a percentage of its own capacity.
    #
    # A percentage rather than a number of litres, because bins are not all the
    # same size: a fixed litres-per-tick rate fills a 660 litre bin more than
    # six times slower in percentage terms, and since every threshold downstream
    # is a percentage, the largest bins would never cross any of them.
    #
    # The defaults are paced for a real bin: at a 5 second interval a bin of any
    # size takes roughly an hour and a quarter to reach a critical level. This
    # matters because the SLA rules downstream allow 2 hours to collect a
    # critical bin - at the old rate a bin overflowed about forty times before
    # one SLA clock expired. See .env.local.example for a faster demo profile.
    FILL_RATE_PCT_MIN: float = 0.02
    FILL_RATE_PCT_MAX: float = 0.15

    # Battery drain per tick, as a percentage. Reaches the 20% maintenance
    # threshold in about two hours, so a run long enough to show a collection
    # also shows a battery alert.
    BATTERY_DRAIN_MIN: float = 0.01
    BATTERY_DRAIN_MAX: float = 0.1

    # A bin is only collected once it is worth collecting.
    #
    # This threshold must sit ABOVE the critical level consumers alert on (80%),
    # or bins are emptied on the way up and never once register as critical -
    # no collection list, no SLA clock, and no fire risk, since that rule needs
    # a bin to be nearly full as well as hot.
    #
    # Emptying at an arbitrary level is also not recognised as a collection
    # downstream, which defines one as a drop from above 60% to below 20%.
    COLLECTION_THRESHOLD_PCT: float = 85.0
    COLLECTION_CHANCE_PCT: int = 5

    # Ambient temperature band for a healthy bin, in Celsius.
    TEMP_NORMAL_MIN: float = 20.0
    TEMP_NORMAL_MAX: float = 35.0

    # Ceiling for a bin with the HOT fault injected. Fire-risk detection looks
    # for temperature above 70 C, so this has to sit above that or the rule
    # could never fire and the detector could never be shown working.
    TEMP_FIRE_MAX: float = 90.0

    # Share of bins that misbehave on purpose. Without faulty bins, the offline,
    # stuck-sensor, duplicate and fire-risk detectors have nothing to detect.
    FAULT_INJECTION_RATE: float = 0.12

    # How many readings a bin with the SILENT fault sends before going quiet.
    #
    # It has to send some. Dead-device detection works by arming a timer when a
    # bin reports and firing when the timer expires, so a bin that never reports
    # at all is not detected as dead - it is simply never known about, and no
    # alert can be raised for a device nothing has ever heard from. A device
    # that reports and then dies is also the realistic failure.
    SILENCE_AFTER_READINGS: int = 10

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
