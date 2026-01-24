import os

class Config:
    # Kafka
    KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    VALID_TOPIC = os.getenv("VALID_TOPIC", "valid-trash-bin-data")
    INVALID_TOPIC = os.getenv("INVALID_TOPIC", "invalid-trash-bin-data")

    # Spark
    CHECKPOINT_MAIN = os.getenv(
        "CHECKPOINT_MAIN",
        "/opt/spark-checkpoints/ward_fill_level_aggregation_v1"
    )
    CHECKPOINT_DLQ = os.getenv(
        "CHECKPOINT_DLQ",
        "/opt/spark-checkpoints/dlq_invalid"
    )
    TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL", "10 seconds")

    # Postgres
    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "trash_bin_db")
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
