# models/bin.py

from datetime import datetime, timezone


class Bin:
    """
    Represents a physical smart waste bin in the simulation.

    This class is the domain model for a smart bin and stores its
    current state, including static metadata (ID, capacity, location, zone)
    and dynamic telemetry attributes (fill level, battery level, and temperature).

    The class is intentionally independent of the simulation engine,
    database, and messaging infrastructure. It does not contain any
    logic for generating telemetry, communicating with Kafka, or
    interacting with PostgreSQL. Those responsibilities belong to
    other components such as `BinSimulator` and `SimulationManager`.

    Attributes:
        bin_id (str):
            Unique identifier of the smart bin.

        capacity (float):
            Maximum capacity of the bin.

        latitude (float):
            Geographic latitude of the bin.

        longitude (float):
            Geographic longitude of the bin.

        zone (str):
            City zone containing the bin.

        current_fill_level (float):
            Current amount of waste in the bin.

        battery_level (float):
            Remaining battery percentage of the bin.

        temperature (float):
            Simulated temperature in degrees Celsius.

        fault_mode (str | None):
            The fault this bin has been told to exhibit, or None for a healthy
            bin. The bin only records the label; acting on it belongs to
            `BinSimulator`, in keeping with this class holding no simulation
            logic. See `simulator.bin_simulator.FAULT_MODES`.

    Methods:
        update_location(latitude, longitude):
            Updates the geographical coordinates of the bin.

        to_payload():
            Returns the current state of the bin as a dictionary
            suitable for serialization and transmission.
    """

    def __init__(
        self,
        bin_id: str,
        capacity: float,
        latitude: float,
        longitude: float,
        zone: str,
        fault_mode: str | None = None,
    ):
        self.bin_id = bin_id
        self.capacity = capacity
        self.latitude = latitude
        self.longitude = longitude
        self.zone = zone
        self.fault_mode = fault_mode

        self.current_fill_level = 0.0
        self.battery_level = 100.0
        self.temperature = 25.0

    @property
    def fill_pct(self) -> float:
        """
        Fill level as a percentage of this bin's capacity.

        Bins are not all the same size, so the raw fill level cannot be compared
        against a percentage threshold directly.
        """
        return self.current_fill_level / self.capacity * 100

    def update_location(self, latitude: float, longitude: float):
        """
        Update the geographical location of the bin.

        Args:
           latitude: New latitude.
           longitude: New longitude.
        """

        self.latitude = latitude
        self.longitude = longitude

    def to_payload(self) -> dict:
        """
        Convert the current state of the bin into a telemetry payload.

        Returns:
            A dictionary containing the latest state of the bin,
            ready to be serialized and published.
        """
        return {
            "bin_id": self.bin_id,
            "capacity": self.capacity,
            "current_fill_level": round(self.current_fill_level, 2),
            "battery_level": round(self.battery_level, 2),
            "temperature": round(self.temperature, 2),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "zone": self.zone,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
