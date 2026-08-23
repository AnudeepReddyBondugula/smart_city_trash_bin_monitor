from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration for the stream processor.

    Mirrors the data-simulator's settings module so both services are configured
    the same way, and so a single .env file can drive the whole stack.
    """

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC: str = "smartbin-telemetry-v1"

    # Messages that cannot be parsed, or that carry a reading no sensor could
    # produce, are published here rather than dropped. A dropped message is
    # invisible; a dead-lettered one can be counted and inspected.
    KAFKA_DLQ_TOPIC: str = "smartbin-telemetry-dlq"

    # Where the streaming queries keep their state. This is not a cache: it
    # holds every SLA clock, every last-seen timestamp and every deduplication
    # key. Deleting it does not reset a query, it erases the memory of the
    # entire fleet. Each query gets its own subdirectory so one can be reset
    # without disturbing the others.
    CHECKPOINT_ROOT: str = "/data/checkpoints"

    # The clean, deduplicated event history. Read by the batch rollup job, and
    # the only place a question nobody has asked yet can still be answered from.
    PARQUET_PATH: str = "/data/bin_events"

    # Telemetry arrives every few seconds, so a ten second batch sees about two
    # readings per bin. Shorter batches cost more database round trips and buy
    # latency nobody asked for.
    TRIGGER_INTERVAL: str = "10 seconds"

    # Without a cap the first batch after any downtime tries to read the entire
    # backlog at once and the job dies on memory. The cap turns a restart into a
    # catch-up that completes over several batches.
    MAX_OFFSETS_PER_TRIGGER: int = 100000

    # How far out of order events may arrive before they are ignored. Also the
    # window over which duplicates are detected.
    WATERMARK: str = "10 minutes"

    # Only consulted when a checkpoint does not exist yet, and on that first
    # start "latest" loses data: the simulator is already publishing while
    # Spark spends tens of seconds building four queries. That window is fatal
    # for a bin that falls silent by design - it publishes its handful of
    # readings, stops forever, and if they landed in the gap it never enters
    # the state store at all, so no offline timeout is ever armed for it.
    # MAX_OFFSETS_PER_TRIGGER keeps the resulting backlog from arriving at once.
    STARTING_OFFSETS: str = "earliest"

    # Local mode: one machine, no master and no workers. A thousand events a
    # second does not need a cluster, and skipping it removes three containers
    # and a network. Add the cluster when one machine measurably runs out.
    SPARK_MASTER: str = "local[*]"
    SPARK_APP_NAME: str = "smartbin-stream-processor"

    # The Spark UI, which is the only place the streaming queries report what
    # they are actually doing: input rate, batch duration, watermark position
    # and state store size per query. Worth having published rather than left
    # inside the container where nothing can reach it.
    SPARK_UI_PORT: int = 4040

    # The batch rollup job gets its own port. It runs alongside the streaming
    # application, and without a separate port it silently lands on whatever
    # Spark finds free after retrying - so the address changes run to run and
    # the log carries a warning that reads like a fault.
    SPARK_BATCH_UI_PORT: int = 4041

    # ---------------------------------------------------------------------
    # Detection thresholds
    #
    # These are the client's rules, in one place, so the numbers a reviewer
    # wants to check are not scattered through the query code.
    # ---------------------------------------------------------------------

    # A bin at or above this is on the collection list.
    CRITICAL_FILL_PCT: float = 80.0

    # At or above this it is overflowing, and on a much shorter clock.
    OVERFLOW_FILL_PCT: float = 95.0

    # Fire risk means hot AND nearly full. Either alone is not an emergency: a
    # hot empty bin is a warm day, and a full cool bin is just a full bin.
    FIRE_RISK_TEMP_C: float = 70.0
    FIRE_RISK_FILL_PCT: float = 80.0

    # Fire risk re-fires on this interval for as long as it stays true, unlike
    # the alerts that fire once on entry. A fire does not stop being urgent
    # because it was already reported.
    FIRE_RISK_REPEAT_MINUTES: float = 5.0

    LOW_BATTERY_PCT: float = 20.0

    # Silent for this long and the device is treated as dead.
    OFFLINE_AFTER_MINUTES: float = 15.0

    # A collection is a large drop, not any drop. Requiring the bin to have been
    # substantially full first separates a truck emptying it from sensor noise
    # or a partial removal.
    COLLECTION_DROP_FROM_PCT: float = 60.0
    COLLECTION_DROP_TO_PCT: float = 20.0

    # A rise larger than this between two consecutive readings is not something
    # a bin fills up by; it is a fault or someone dumping a load.
    ANOMALY_JUMP_PCT: float = 30.0

    # Identical consecutive readings before the sensor is called stuck. A real
    # bin's fill level moves a little every reading, so a value that has not
    # changed at all this many times has frozen.
    STUCK_READING_COUNT: int = 20

    # Time allowed to collect a bin once it crosses each threshold, from the
    # client's service level rules.
    SLA_CRITICAL_MINUTES: float = 120.0
    SLA_OVERFLOW_MINUTES: float = 30.0

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """A psycopg2 connection URL.

        Note this is the plain driver, not the async one the simulator uses:
        writes happen inside Spark executors, which are threads, not an event
        loop.
        """
        return (
            f"postgresql://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def CONTRACT_PATH(self) -> Path:
        """The shared telemetry contract.

        Checked into the repository root and copied into the image, so both
        services build their view of the payload from one file.
        """
        service_root = Path(__file__).resolve().parents[1]

        # Walk upwards rather than naming fixed candidates, because the layout
        # differs: in the image the contract sits beside the service at /app,
        # while in the repository it is two levels up at the root. Searching
        # upwards covers both without either having to know about the other.
        for base in (service_root, *service_root.parents):
            candidate = base / "contracts" / "telemetry-v1.json"
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(
            f"telemetry contract not found searching upwards from {service_root}"
        )

    def checkpoint_for(self, query_name: str) -> str:
        """The checkpoint directory belonging to one named query."""
        return f"{self.CHECKPOINT_ROOT}/{query_name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
