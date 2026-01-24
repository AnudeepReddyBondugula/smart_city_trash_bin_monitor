import threading
import time
import random
from datetime import datetime, timezone
import json
from kafka import KafkaProducer # type: ignore
from kafka.errors import NoBrokersAvailable #type:ignore

class VirtualTrashBin(threading.Thread):

    def __init__(self, bin_id, latitude=None, longitude=None, ward=None, interval=5, error_freq=0.2, bootstrap_servers='localhost:9092'):
        super().__init__()
        self.bin_id = bin_id
        self.latitude = latitude if latitude is not None else round(random.uniform(12.90, 12.99), 6)  # Example: Bangalore area
        self.longitude = longitude if longitude is not None else round(random.uniform(77.50, 77.70), 6)
        self.ward = ward if ward is not None else random.randint(1, 100)
        self.interval = interval
        self.error_freq = error_freq
        self._stop_event = threading.Event()

        self.fill_level = random.randint(0, 20)
        self.temperature = round(random.uniform(25.0, 30.0), 1)
        self.humidity = random.randint(40, 60)

        self.data_attributes = ["bin_id", "timestamp", "fill_level", "latitude", "longitude", "humidity", "temperature", "ward"]

        self.bootstrap_servers = bootstrap_servers
        self.producer = self.get_kafka_producer()
        self.TOPIC = "raw-trash-bin-data"

    def update_values(self):

        if self.fill_level < 100:
            self.fill_level += random.uniform(0, 5)
        
        if self.fill_level > 100:
            self.fill_level = 100

        # Slight random fluctuations in environment
        self.temperature += round(random.uniform(-0.5, 0.5), 1)
        self.temperature = min(max(self.temperature, 20), 45)

        self.humidity += random.randint(-2, 2)
        self.humidity = min(max(self.humidity, 30), 90)

    def generate_data(self):

            # {
            #   "bin_id": "B001",
            #   "latitude": 12.9716,
            #   "longitude": 77.5946,
            #   "ward": 5,
            #   "fill_level": 94,
            #   "temperature": 32.5,
            #   "humidity": 65,
            #   "timestamp": "2025-05-12T10:30:00Z"
            # }

        data = {
            "bin_id": self.bin_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fill_level": self.fill_level,
            "temperature": self.temperature,
            "humidity" : self.humidity,
            "langitude" : self.latitude,
            "longitude" : self.longitude,
            "ward" : self.ward
        }

        # Also need to update the values for the next Interval
        self.update_values()

        if random.random() < self.error_freq:
            data = self.make_invalid_data(data)

        return data
    

    # Kafka Handling Section

    def get_kafka_producer(self, retries=10, delay=5):
        """Retry logic for KafkaProducer connection"""
        for attempt in range(1, retries + 1):
            try:
                print(f"[INFO] Connecting to Kafka ({attempt}/{retries})...")
                return KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8")
                )
            except NoBrokersAvailable as e:
                print(f"[WARN] Kafka unavailable: {e}")
                time.sleep(delay)
        print("[ERROR] Kafka connection failed after retries. Exiting.")
        return None

    # Invalid Data Making Section
    def make_invalid_data(self, data):
        x = random.randint(1, len(self.data_attributes)) # Number of attributes to modify
        selected_attributes = random.sample(self.data_attributes, x) # randomly selecting x number of attributes

        for attribute in selected_attributes:
            if attribute == 'bin_id':
                data = self.make_invalid_bin_id_data(data)
            
            elif attribute == 'latitude':
                data = self.make_invalid_latitude_data(data)

            elif attribute == 'longitude':
                data = self.make_invalid_longitude_data(data)

            elif attribute == 'ward':
                data = self.make_invalid_ward_data(data)

            elif attribute == 'fill_level':
                data = self.make_invalid_fill_level_data(data)

            elif attribute == 'temperature':
                data = self.make_invalid_temperature_data(data)

            elif attribute == 'humidity':
                data = self.make_invalid_humidity_data(data)

            elif attribute == 'timestamp':
                data = self.make_invalid_timestamp_data(data)

        return data



    def make_invalid_bin_id_data(self, data):
        data['bin_id'] = None
        return data


    def make_invalid_latitude_data(self, data):
        choice = random.randint(0, 2)

        if choice == 0:
            data['latitude'] = None
        
        elif choice == 1:
            data['latitude'] = random.choice([
                                    round(random.uniform(-180, -90.1), 6),
                                    round(random.uniform(90.1, 180), 6)
                                ])
            
        elif choice == 2:
            data['latitude'] = random.choice(["north", "abc", "", "NaN"])

        return data


    def make_invalid_longitude_data(self, data):
        choice = random.randint(0, 2)

        if choice == 0:
            data['longitude'] = None
        
        elif choice == 1:
            data['longitude'] = random.choice([
                                    round(random.uniform(-300, -180.1), 6),
                                    round(random.uniform(180.1, 300), 6)
                                ])
            
        elif choice == 2:
            data['longitude'] = random.choice(["north", "abc", "", "NaN"])

        return data


    def make_invalid_ward_data(self, data):
        
        choice = random.randint(0, 2)

        if choice == 0:
            data['ward'] = None
        
        elif choice == 1:
            data['ward'] = random.randint(-1000, 0)

        elif choice == 2:
            data['ward'] = random.choice([12.34, "five", "", [], {}, "NaN"])

        return data


    def make_invalid_fill_level_data(self, data):
        choice = random.randint(0, 2)

        if choice == 0:
            data['fill_level'] = None

        elif choice == 1:
            data['fill_level'] = random.choice([
                random.randint(-100, -1),
                random.randint(101, 200)
            ])

        elif choice == 2:
            data['fill_level'] = random.choice(["five", "", [], {}, "NaN"])

        return data


    def make_invalid_temperature_data(self, data):
        choice = random.randint(0, 2)

        if choice == 0:
            data['temperature'] = None
        
        elif choice == 1:
            data['temperature'] = random.choice([
                random.randint(-1000, 49),
                random.randint(81, 1000)
            ])

        elif choice == 2:
            data['temperature'] = random.choice(["five", "", [], {}, "NaN"])

        return data


    def make_invalid_humidity_data(self, data):

        choice = random.randint(0, 2)

        if choice == 0:
            data['humidity'] = None
        
        elif choice == 1:
            data['humidity'] = random.choice([
                random.randint(-1000, -1),
                random.randint(101, 1000)
            ])

        elif choice == 2:
            data['humidity'] = random.choice([12.34, "five", "", [], {}, "NaN"])
        return data


    def make_invalid_timestamp_data(self, data):
        choice = random.randint(0, 1)

        if choice == 0:
            data['timestamp'] = None

        elif choice == 1:
            data['timestamp'] = random.choice([12.34, "five", "", [], {}, "NaN"])
        return data



    # Thread State handler Section

    def run(self):
        print(f'[INFO] Bin {self.bin_id} started')
        while not self._stop_event.is_set():
            time.sleep(self.interval + random.randint(-1 * self.interval, self.interval))
            data = self.generate_data()
            print(f'[INFO] [{self.bin_id}] {data}')
            while self.producer is None:
                self.producer = self.get_kafka_producer()
            self.producer.send(self.TOPIC, value=data)
        print(f'[INFO] Bin {self.bin_id} stopped')


    def stop(self):
        self._stop_event.set()
        print(f'[INFO] Bin {self.bin_id} stopping')

    
