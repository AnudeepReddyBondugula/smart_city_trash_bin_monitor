import pytest
from src.models.bin import Bin
from datetime import datetime

def test_bin_initialization():
    """
    Test the initialization of a Bin model.
    Verifies that static metadata (ID, capacity, coordinates) are set correctly,
    and that dynamic telemetry attributes (fill level, battery) are given proper defaults.
    """
    b = Bin("bin_1", 100.0, 10.0, 20.0)
    assert b.bin_id == "bin_1"
    assert b.capacity == 100.0
    assert b.latitude == 10.0
    assert b.longitude == 20.0
    assert b.current_fill_level == 0.0
    assert b.battery_level == 100.0

def test_update_location():
    """
    Test the update_location method of the Bin model.
    Ensures that calling this method correctly updates the latitude and longitude.
    """
    b = Bin("bin_1", 100.0, 10.0, 20.0)
    b.update_location(30.0, 40.0)
    assert b.latitude == 30.0
    assert b.longitude == 40.0

def test_to_payload():
    """
    Test the to_payload method of the Bin model.
    Verifies that it generates a properly formatted dictionary payload for telemetry,
    including rounding values and generating a valid ISO 8601 timestamp.
    """
    b = Bin("bin_1", 100.0, 10.0, 20.0)
    b.current_fill_level = 50.123
    b.battery_level = 80.456
    
    payload = b.to_payload()
    
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
