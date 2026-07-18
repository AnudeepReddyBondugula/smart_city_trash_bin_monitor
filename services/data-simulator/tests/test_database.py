import pytest
from src.database import SmartBin
from sqlalchemy import inspect

def test_smart_bin_model():
    """
    Test the creation of a SmartBin database model instance.
    Verifies that providing standard constructor arguments correctly maps
    to the attributes defined on the SQLAlchemy declarative base.
    """
    bin_instance = SmartBin(
        bin_id="bin_db_1",
        capacity=100.0,
        latitude=10.0,
        longitude=20.0
    )
    
    assert bin_instance.bin_id == "bin_db_1"
    assert bin_instance.capacity == 100.0
    assert bin_instance.latitude == 10.0
    assert bin_instance.longitude == 20.0


def test_smart_bin_model_columns():
    """
    Test the SmartBin model metadata directly via SQLAlchemy inspection,
    ensuring columns and default constraints exist without needing a database.
    """
    mapper = inspect(SmartBin)
    
    # Verify primary key
    assert mapper.primary_key[0].name == "bin_id"
    
    # Verify columns exist
    columns = mapper.columns
    assert "capacity" in columns
    assert "latitude" in columns
    assert "longitude" in columns
    assert "status" in columns
    
    # Verify constraints/defaults statically
    assert columns["capacity"].nullable is False
    assert columns["status"].default.arg == "ACTIVE"
