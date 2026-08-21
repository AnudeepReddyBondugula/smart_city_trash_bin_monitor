from src.database import SmartBin
from sqlalchemy import inspect
from sqlalchemy import String

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
        longitude=20.0,
        zone="NORTH",
    )
    
    assert bin_instance.bin_id == "bin_db_1"
    assert bin_instance.capacity == 100.0
    assert bin_instance.latitude == 10.0
    assert bin_instance.longitude == 20.0
    assert bin_instance.zone == "NORTH"


def test_tablename_is_smart_bins():
    """
    Test that the SmartBin ORM model maps to the correct table name.
    """
    assert SmartBin.__tablename__ == "smart_bins"


def test_bin_id_primary_key_string_type():
    """
    Test that bin_id is the primary key and is backed by a bounded String type.
    """
    columns = inspect(SmartBin).columns

    bin_id_col = columns["bin_id"]
    assert bin_id_col.primary_key is True
    assert isinstance(bin_id_col.type, String)
    assert bin_id_col.type.length == 50


def test_timestamp_columns_exist():
    """
    Test that created_at and updated_at columns exist, are non-nullable,
    and carry server-side defaults.
    """
    columns = inspect(SmartBin).columns

    for col_name in ("created_at", "updated_at"):
        assert col_name in columns, f"Missing expected column: {col_name}"
        col = columns[col_name]
        assert col.nullable is False
        # Both columns rely on the DB server default (func.now())
        assert col.server_default is not None


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
    assert "zone" in columns
    assert "status" in columns
    
    # Verify constraints/defaults statically
    assert columns["capacity"].nullable is False
    assert columns["zone"].nullable is False
    assert isinstance(columns["zone"].type, String)
    assert columns["zone"].type.length == 20
    # Python-side default for status is the string "ACTIVE"
    status_default = columns["status"].default
    assert status_default is not None
    assert getattr(status_default, "arg", None) == "ACTIVE"
