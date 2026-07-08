import asyncio
import logging
from datetime import datetime, timezone
from faker import Faker
from .config import settings
from .kafka_producer import kafka_client

logger = logging.getLogger(__name__)
fake = Faker()

class BinSimulator:
    def __init__(self, bin_id: str, capacity: float, latitude: float, longitude: float):
        self.bin_id = bin_id
        self.capacity = capacity
        self.latitude = latitude
        self.longitude = longitude
        self.current_fill_level = 0.0
        self.battery_level = 100.0
        self._task = None
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._simulate_loop())
            logger.info(f"Started simulation for bin {self.bin_id}")

    async def stop(self):
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info(f"Stopped simulation for bin {self.bin_id}")

    def update_location(self, lat: float, lon: float):
        self.latitude = lat
        self.longitude = lon
        logger.debug(f"Updated location for bin {self.bin_id}: {lat}, {lon}")

    async def _simulate_loop(self):
        try:
            while self._running:
                # Simulate fill level increasing, occasionally emptying
                if fake.boolean(chance_of_getting_true=5):  # 5% chance to empty
                    self.current_fill_level = 0.0
                else:
                    increase = fake.pyfloat(min_value=0.5, max_value=5.0)
                    self.current_fill_level = min(self.capacity, self.current_fill_level + increase)

                # Battery drains slowly
                self.battery_level = max(0.0, self.battery_level - fake.pyfloat(min_value=0.01, max_value=0.1))

                payload = {
                    "bin_id": self.bin_id,
                    "capacity": self.capacity,
                    "current_fill_level": round(self.current_fill_level, 2),
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "battery_level": round(self.battery_level, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                await kafka_client.send_telemetry(self.bin_id, payload)
                await asyncio.sleep(settings.TELEMETRY_INTERVAL_SEC)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in simulation loop for bin {self.bin_id}: {e}")
            self._running = False
