import logging
from datetime import datetime, timezone
from faker import Faker

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

    def update_location(self, lat: float, lon: float):
        self.latitude = lat
        self.longitude = lon
        logger.debug(f"Updated location for bin {self.bin_id}: {lat}, {lon}")


    def generate_payload(self) -> dict:
        # Simulate fill level increasing, occasionally emptying
        if fake.boolean(chance_of_getting_true=5):  # 5% chance to empty
            self.current_fill_level = 0.0
        else:
            increase = fake.pyfloat(min_value=0.5, max_value=5.0)
            self.current_fill_level = min(self.capacity, self.current_fill_level + increase)

        # Battery drains slowly
        self.battery_level = max(0.0, self.battery_level - fake.pyfloat(min_value=0.01, max_value=0.1))

        return {
            "bin_id": self.bin_id,
            "capacity": self.capacity,
            "current_fill_level": round(self.current_fill_level, 2),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "battery_level": round(self.battery_level, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
