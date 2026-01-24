import os


def required_env(name: str) -> str:
    """
    Fetch a required environment variable.
    Fail fast if it is missing.
    """
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"❌ Missing required environment variable: {name}")
    return value


# =========================
# Kafka Configuration
# =========================
KAFKA_BOOTSTRAP_SERVERS = required_env("KAFKA_BOOTSTRAP_SERVERS")
VALID_TOPIC = required_env("VALID_TOPIC")
INVALID_TOPIC = required_env("INVALID_TOPIC")


# =========================
# Simulator Configuration
# =========================
DATA_INTERVAL_SECONDS = int(os.getenv("DATA_INTERVAL_SECONDS", "10"))
ERROR_FREQ = float(os.getenv("ERROR_FREQ", "0.2"))


# =========================
# Smart Bin Configuration
# =========================
BIN_IDS = ["B001", "B002", "B003", "B004"]
WARDS = [1, 2, 3, 4, 5]

# =========================
# PostgreSQL Configuration
# =========================

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "trash_bin_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")


LATITUDE_RANGE = (12.9500, 12.9900)
LONGITUDE_RANGE = (77.5800, 77.6100)

FILL_LEVEL_RANGE = (0, 100)          # %
TEMPERATURE_RANGE = (20.0, 40.0)     # °C
HUMIDITY_RANGE = (30, 90)            # %

ERROR_TYPES = [
    "null",
    "out_of_range",
    "timestamp_skew",
    "incomplete",
    "corrupted"
]
