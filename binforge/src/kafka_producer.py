import json
import logging
from aiokafka import AIOKafkaProducer
from .config import settings

logger = logging.getLogger(__name__)

class KafkaClient:
    def __init__(self):
        self.producer = None
    
    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info(f"Kafka producer started on {settings.KAFKA_BROKERS}")

    async def stop(self):
        await self.producer.stop()
        logger.info("Kafka producer stopped")

    async def send_telemetry(self, bin_id: str, payload: dict):
        try:
            await self.producer.send_and_wait(
                topic=settings.KAFKA_TOPIC,
                value=payload,
                key=bin_id.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Failed to send telemetry for {bin_id}: {e}")

kafka_client = KafkaClient()
