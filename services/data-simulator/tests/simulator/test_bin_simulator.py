import pytest
from unittest.mock import patch, AsyncMock
from src.models.bin import Bin
from src.simulator.bin_simulator import BinSimulator

@pytest.fixture
def bin_instance():
    return Bin("bin_1", 100.0, 10.0, 20.0, "NORTH")

@pytest.mark.asyncio
async def test_start_and_stop(bin_instance):
    """
    Test the start and stop lifecycle methods of the BinSimulator.
    Ensures that start() creates a background task and marks the simulator as running,
    while stop() gracefully cancels the task and resets the running state.
    """
    simulator = BinSimulator(bin_instance)
    assert not simulator._running
    
    simulator.start()
    assert simulator._running
    assert simulator._task is not None
    assert not simulator._task.done()
    
    await simulator.stop()
    assert not simulator._running
    assert simulator._task.done()

@pytest.mark.asyncio
async def test_stop_when_already_stopped(bin_instance, caplog):
    """
    Test that stopping a simulator which is not running is a safe no-op.
    Verifies a warning is logged and no task cancellation is attempted.
    """
    simulator = BinSimulator(bin_instance)
    assert not simulator._running

    await simulator.stop()

    assert not simulator._running
    assert simulator._task is None
    assert "Simulator for bin 'bin_1' is already stopped." in caplog.text

@pytest.mark.asyncio
async def test_start_already_running(bin_instance, caplog):
    """
    Test that starting an already running simulator does not spawn additional
    tasks, but instead logs a warning message and safely ignores the request.
    """
    simulator = BinSimulator(bin_instance)
    simulator.start()
    task1 = simulator._task
    
    # Try starting again
    simulator.start()
    assert simulator._task is task1
    assert "Simulator is already running" in caplog.text
    
    await simulator.stop()

@patch('src.simulator.bin_simulator.uniform', return_value=0.5)
@patch('src.simulator.bin_simulator.fake')
def test_simulate_normal_behavior(mock_fake, mock_uniform, bin_instance):
    """
    Test the _simulate method during standard operation.
    Validates that the bin's fill level appropriately increases and the battery
    level decreases by random values bounded by expected constraints.
    """
    simulator = BinSimulator(bin_instance)
    bin_instance.current_fill_level = 50.0
    bin_instance.battery_level = 80.0
    
    # Not emptying the bin
    mock_fake.boolean.return_value = False
    mock_fake.pyfloat.side_effect = [5.0, 0.1]
    
    simulator._simulate()
    
    assert bin_instance.current_fill_level == 55.0
    assert bin_instance.battery_level == 79.9
    assert bin_instance.temperature == 25.5

@patch('src.simulator.bin_simulator.fake')
def test_simulate_empty_bin(mock_fake, bin_instance):
    """
    Test the _simulate method when a bin empty event occurs.
    Validates the edge case where the bin is emptied by waste collection,
    ensuring the fill level resets to exactly 0.0.
    """
    simulator = BinSimulator(bin_instance)
    bin_instance.current_fill_level = 50.0
    
    # Emptying the bin
    mock_fake.boolean.return_value = True
    mock_fake.pyfloat.return_value = 0.1
    
    simulator._simulate()
    
    assert bin_instance.current_fill_level == 0.0

@pytest.mark.asyncio
@patch('src.simulator.bin_simulator.kafka_client')
@patch('src.simulator.bin_simulator.asyncio.sleep')
async def test_run_loop(mock_sleep, mock_kafka_client, bin_instance):
    """
    Test the asynchronous _run execution loop of the BinSimulator.
    Verifies that it repeatedly generates a payload and publishes it using the
    Kafka client, sleeping between iterations.
    """
    mock_kafka_client.send_telemetry = AsyncMock()
    simulator = BinSimulator(bin_instance)
    simulator._running = True
    
    # We want to run the loop exactly once
    async def stop_simulator(*args, **kwargs):
        simulator._running = False
        
    mock_sleep.side_effect = stop_simulator
    
    await simulator._run()
    
    # check that we sent a dict object mapping what bin.to_payload() returns
    # The payload is dynamic (due to timestamp), so we just check that send_telemetry was called
    mock_kafka_client.send_telemetry.assert_called_once()
    args, _ = mock_kafka_client.send_telemetry.call_args
    assert args[0] == "bin_1"
    assert "timestamp" in args[1]
    mock_sleep.assert_called_once()

@patch('src.simulator.bin_simulator.fake')
def test_simulate_reaches_capacity(mock_fake, bin_instance):
    """
    Test that the fill level does not exceed the bin's maximum capacity.
    """
    simulator = BinSimulator(bin_instance)
    bin_instance.current_fill_level = 98.0
    bin_instance.capacity = 100.0
    
    mock_fake.boolean.return_value = False
    mock_fake.pyfloat.side_effect = [5.0, 0.1]
    
    simulator._simulate()
    
    assert bin_instance.current_fill_level == 100.0

@patch('src.simulator.bin_simulator.fake')
def test_simulate_battery_depletion(mock_fake, bin_instance):
    """
    Test that the battery level does not drop below 0.0.
    """
    simulator = BinSimulator(bin_instance)
    bin_instance.battery_level = 0.05
    
    mock_fake.boolean.return_value = False
    mock_fake.pyfloat.side_effect = [5.0, 0.1]
    
    simulator._simulate()
    
    assert bin_instance.battery_level == 0.0


@pytest.mark.parametrize(
    ("starting_temperature", "change", "expected"),
    [(34.8, 0.5, 35.0), (20.2, -0.5, 20.0)],
)
@patch('src.simulator.bin_simulator.uniform')
@patch('src.simulator.bin_simulator.fake')
def test_simulate_clamps_temperature(
    mock_fake, mock_uniform, bin_instance, starting_temperature, change, expected
):
    """Temperature remains inside the supported Celsius range."""
    bin_instance.temperature = starting_temperature
    mock_fake.boolean.return_value = False
    mock_fake.pyfloat.side_effect = [1.0, 0.1]
    mock_uniform.return_value = change

    BinSimulator(bin_instance)._simulate()

    assert bin_instance.temperature == expected
