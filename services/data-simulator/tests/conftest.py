import os

# Set dummy environment variables for pydantic settings validation during tests
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "test_db"
os.environ["POSTGRES_USER"] = "test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
os.environ["KAFKA_TOPIC"] = "simulated_telemetry"

def pytest_itemcollected(item):
    """
    Modifies the test node ID to include its docstring.
    This ensures that when pytest is run in verbose mode, 
    the docstring comments are printed alongside the test result.
    """
    if getattr(item, "obj", None) and item.obj.__doc__:
        # Get the first descriptive line of the docstring
        doc_lines = [line.strip() for line in item.obj.__doc__.strip().split('\n') if line.strip()]
        if doc_lines:
            doc = doc_lines[0]
            # Format the output so it looks like: test_file.py::test_name [ Docstring ]
            item._nodeid = f"{item.nodeid} \n      > {doc}"
