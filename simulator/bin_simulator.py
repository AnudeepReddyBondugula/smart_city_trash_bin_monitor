import sys
import time
import json
import random
import threading
from datetime import datetime, timezone, timedelta
from kafka import KafkaProducer # type: ignore
from kafka.errors import NoBrokersAvailable #type:ignore
import config
from psycopg2.pool import SimpleConnectionPool

stop_event = threading.Event()
trigger_event = threading.Event()

# Postgres Connection Pool Initialization
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=config.DB_HOST,
    port=config.DB_PORT,
    database=config.DB_NAME,
    user=config.DB_USER,
    password=config.DB_PASSWORD
)

# Function to register bins in the database
def register_bin(ward: int, bin_id: str):
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ward_bins (ward, bin_id)
                VALUES (%s, %s)
                ON CONFLICT (ward, bin_id) DO NOTHING;
                """,
                (ward, bin_id)
            )
        conn.commit()  # ensure changes are saved
    except Exception as e:
        print(f"[ERROR] Failed to register bin {bin_id} in ward {ward}: {e}")
    finally:
        pool.putconn(conn)  # return connection to pool
        print("done")


def get_kafka_producer(bootstrap_servers, retries=10, delay=5):
    """Retry logic for KafkaProducer connection"""
    for attempt in range(1, retries + 1):
        try:
            print(f"[INFO] Connecting to Kafka ({attempt}/{retries})...")
            return KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
        except NoBrokersAvailable as e:
            print(f"[WARN] Kafka unavailable: {e}")
            time.sleep(delay)
    print("[ERROR] Kafka connection failed after retries. Exiting.")
    sys.exit(1)

# Initialize Kafka producer
producer = get_kafka_producer(config.KAFKA_BOOTSTRAP_SERVERS)

# Predefined metadata for bins
bin_metadata = {
    bin_id: {
        "latitude": round(random.uniform(*config.LATITUDE_RANGE), 6),
        "longitude": round(random.uniform(*config.LONGITUDE_RANGE), 6),
        "ward": random.choice(config.WARDS)
    }
    for bin_id in config.BIN_IDS
}

def generate_valid_record(bin_id):
    """Generates a valid smart bin record"""
    meta = bin_metadata[bin_id]
    return {
        "bin_id": bin_id,
        "latitude": meta["latitude"],
        "longitude": meta["longitude"],
        "ward": meta["ward"],
        "fill_level": random.randint(*config.FILL_LEVEL_RANGE),
        "temperature": round(random.uniform(*config.TEMPERATURE_RANGE), 1),
        "humidity": random.randint(*config.HUMIDITY_RANGE),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

def introduce_data_issues(record):
    """Introduces issues into a smart bin record"""
    issue_type = random.choice(config.ERROR_TYPES)

    if issue_type == "null":
        record[random.choice(["fill_level", "humidity", "temperature"])] = None
    elif issue_type == "out_of_range":
        field = random.choice(["fill_level", "humidity"])
        record[field] = 150 if field == "fill_level" else -20
    elif issue_type == "timestamp_skew":
        skew_days = random.choice([-365, 365])
        record["timestamp"] = (
            datetime.now(timezone.utc) + timedelta(days=skew_days)
        ).isoformat().replace("+00:00", "Z")
    elif issue_type == "incomplete":
        for field in random.sample(
            [k for k in record if k != "bin_id"], min(3, len(record) - 1)
        ):
            record.pop(field, None)
    elif issue_type == "corrupted":
        record["fill_level"] = "high"

    return record

def bin_worker(bin_id):
    """Thread function for generating bin data"""
    while not stop_event.is_set():
        if trigger_event.wait(timeout=1):
            try:
                record = generate_valid_record(bin_id)

                if random.random() < config.ERROR_FREQ:
                    invalid_record = introduce_data_issues(record.copy())
                    topic = config.INVALID_TOPIC
                    print(f"[DEBUG] Invalid record for bin {bin_id}")
                    producer.send(topic, value=invalid_record)
                    print(f"[{topic}] {json.dumps(invalid_record)}")
                else:
                    register_bin(record["ward"], bin_id)        # Register bin in DB
                    topic = config.VALID_TOPIC
                    producer.send(topic, value=record)
                    print(f"[{topic}] {json.dumps(record)}")

            except Exception as e:
                print(f"[ERROR] Bin {bin_id} error: {e}")
            trigger_event.clear()

def main():
    print(f"\n[INFO] Starting Smart Bin Simulator with {len(config.BIN_IDS)} bins")
    print(f"[INFO] Sending data every {config.DATA_INTERVAL_SECONDS} seconds\n")

    threads = [
        threading.Thread(target=bin_worker, args=(bin_id,), daemon=True)
        for bin_id in config.BIN_IDS
    ]

    for thread in threads:
        thread.start()

    try:
        while not stop_event.is_set():
            trigger_event.set()
            time.sleep(0.5)
            time.sleep(config.DATA_INTERVAL_SECONDS - 0.5)
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C received. Shutting down...")
        stop_event.set()

    time.sleep(1)
    producer.close()
    print("[INFO] Simulator stopped.")

if __name__ == "__main__":
    main()
