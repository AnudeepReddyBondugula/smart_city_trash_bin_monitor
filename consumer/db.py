import os
import json
import psycopg2


class PostgresWriter:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()

    def insert_valid(self, data: dict):
        query = """
            INSERT INTO valid_trash_bin_events (
                bin_id, latitude, longitude, ward,
                fill_level, temperature, humidity, event_time
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (bin_id, event_time) DO NOTHING
        """

        self.cur.execute(query, (
            data["bin_id"],
            data["latitude"],
            data["longitude"],
            data["ward"],
            data["fill_level"],
            data["temperature"],
            data["humidity"],
            data["timestamp"],
        ))

    def insert_invalid(self, data: dict, reason="validation_error"):
        query = """
            INSERT INTO invalid_trash_bin_events (
                bin_id,
                raw_payload,
                error_reason,
                event_time
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (bin_id, event_time) DO NOTHING;
        """
        self.cur.execute(query, (
            data.get("bin_id"),
            json.dumps(data),
            reason,
            data.get("timestamp"),
        ))
