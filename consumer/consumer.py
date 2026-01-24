from kafka import KafkaConsumer  # pyright: ignore
import json
import os
import db


class TrashBinConsumer:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        self.topics = [
            os.getenv("VALID_TOPIC"),
            os.getenv("INVALID_TOPIC"),
        ]
        self.group_id = os.getenv("CONSUMER_GROUP_ID")

        print("🚀 Initializing Kafka Consumer")
        print("Kafka Broker :", self.bootstrap_servers)
        print("Subscribed Topics :", self.topics)
        print("Consumer Group ID :", self.group_id)

        # Initialize Postgres writer
        self.db = db.PostgresWriter()

        # Create Kafka consumer
        self.consumer = KafkaConsumer(
            *self.topics,  # multiple topics
            bootstrap_servers=[self.bootstrap_servers],
            group_id=self.group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

    def process_message(self, message):
        """
        Handle a single Kafka message
        """
        try:
            topic = message.topic
            data = message.value

            if topic == "valid-trash-bin-data":
                self.db.insert_valid(data)
                print(f"✅ VALID DATA  : {data}")

            elif topic == "invalid-trash-bin-data":
                self.db.insert_invalid(data)
                print(f"❌ INVALID DATA: {data}")

            else:
                print(f"⚠️ UNKNOWN TOPIC {topic}: {data}")

            self.consumer.commit()
            print("Consumer Offset committed")

        except Exception as e:
            print("Error processing message or failed to insert data:", e)

    def start(self):
        """
        Start consuming messages
        """
        print("📡 Consumer started. Waiting for messages...\n")

        try:
            for message in self.consumer:
                self.process_message(message)

        except KeyboardInterrupt:
            print("\n🛑 Consumer stopped manually")

        finally:
            self.consumer.close()
            print("🔒 Kafka consumer closed")

if __name__ == "__main__":
    consumer_app = TrashBinConsumer()
    consumer_app.start()
