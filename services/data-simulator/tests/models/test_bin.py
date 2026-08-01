import pytest
from src.models.bin import Bin
from datetime import datetime

@pytest.fixture
def bin_instance():
    """Provides a fresh Bin instance for each test."""
    return Bin("bin_1", 100.0, 10.0, 20.0)

def test_bin_initialization(bin_instance):
    """
    Test the initialization of a Bin model.
    Verifies that static metadata (ID, capacity, coordinates) are set correctly,
    and that dynamic telemetry attributes (fill level, battery) are given proper defaults.
    """
    assert bin_instance.bin_id == "bin_1"
    assert bin_instance.capacity == 100.0
    assert bin_instance.latitude == 10.0
    assert bin_instance.longitude == 20.0
    assert bin_instance.current_fill_level == 0.0
    assert bin_instance.battery_level == 100.0

def test_update_location(bin_instance):
    """
    Test the update_location method of the Bin model.
    Ensures that calling this method correctly updates the latitude and longitude.
    """
    bin_instance.update_location(30.0, 40.0)
    assert bin_instance.latitude == 30.0
    assert bin_instance.longitude == 40.0

def test_to_payload(bin_instance):
    """
    Test the to_payload method of the Bin model.
    Verifies that it generates a properly formatted dictionary payload for telemetry,
    including rounding values and generating a valid ISO 8601 timestamp.
    """
    bin_instance.current_fill_level = 50.123
    bin_instance.battery_level = 80.456
    
    payload = bin_instance.to_payload()
    
    assert payload["bin_id"] == "bin_1"
    assert payload["capacity"] == 100.0
    assert payload["current_fill_level"] == 50.12
    assert payload["battery_level"] == 80.46
    assert payload["latitude"] == 10.0
    assert payload["longitude"] == 20.0
    
    # check timestamp is iso format
    timestamp = payload.get("timestamp")
    assert timestamp is not None
    # datetime.fromisoformat should not raise an error
    datetime.fromisoformat(timestamp)
    # Per the Bin contract, the timestamp is UTC (timezone-aware, +00:00 offset)
    assert timestamp.endswith("+00:00")
