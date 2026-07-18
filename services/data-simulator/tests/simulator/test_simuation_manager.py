import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.simulator.simuation_manager import SimulationManager
from src.models.bin import Bin
from src.database import SmartBin

@pytest.fixture
def sim_manager():
    return SimulationManager()

@pytest.fixture
def bin_instance():
    return Bin("bin_1", 100.0, 10.0, 20.0)

@pytest.mark.asyncio
@patch('src.simulator.simuation_manager.AsyncSessionLocal')
async def test_initialize(mock_session_maker, sim_manager):
    """
    Test the initialization of the SimulationManager from the database.
    Verifies that it loads ACTIVE bins from the database, spawns a simulator
    for each one, and successfully starts them.
    """
    # Mocking database response
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_result = MagicMock()
    mock_db_bin = SmartBin(bin_id="db_bin_1", latitude=1.0, longitude=2.0, capacity=50.0, status="ACTIVE")
    mock_result.scalars().all.return_value = [mock_db_bin]
    mock_session.execute.return_value = mock_result
    
    with patch('src.simulator.simuation_manager.BinSimulator') as MockSimulator:
        mock_sim_instance = MagicMock()
        MockSimulator.return_value = mock_sim_instance
        
        await sim_manager.initialize()
        
        assert len(sim_manager._simulators) == 1
        assert "db_bin_1" in sim_manager._simulators
        mock_sim_instance.start.assert_called_once()

def test_add_bin(sim_manager, bin_instance):
    """
    Test adding a new bin to the SimulationManager.
    Ensures that it correctly instantiates a BinSimulator, starts it, 
    and registers it within the active simulators dictionary.
    """
    with patch('src.simulator.simuation_manager.BinSimulator') as MockSimulator:
        mock_sim_instance = MagicMock()
        MockSimulator.return_value = mock_sim_instance
        
        sim_manager.add_bin(bin_instance)
        
        assert "bin_1" in sim_manager._simulators
        mock_sim_instance.start.assert_called_once()
        
def test_add_bin_already_exists(sim_manager, bin_instance, caplog):
    """
    Test adding a bin that is already actively managed by the SimulationManager.
    Ensures it logs a warning instead of overwriting the existing simulator.
    """
    sim_manager._simulators["bin_1"] = MagicMock()
    
    sim_manager.add_bin(bin_instance)
    assert "Simulator already exists" in caplog.text

@pytest.mark.asyncio
async def test_remove_bin(sim_manager):
    """
    Test removing an existing bin from the SimulationManager.
    Verifies that the target simulator is gracefully stopped and fully 
    removed from the active registry.
    """
    mock_simulator = AsyncMock()
    sim_manager._simulators["bin_1"] = mock_simulator
    
    await sim_manager.remove_bin("bin_1")
    
    assert "bin_1" not in sim_manager._simulators
    mock_simulator.stop.assert_called_once()

@pytest.mark.asyncio
async def test_remove_bin_not_found(sim_manager, caplog):
    """
    Test attempting to remove a bin that does not exist in the manager.
    Verifies that it logs a warning and exits safely without errors.
    """
    await sim_manager.remove_bin("nonexistent")
    assert "No simulator found" in caplog.text

def test_update_bin(sim_manager, bin_instance):
    """
    Test updating the coordinates of an actively simulated bin.
    Ensures the manager retrieves the corresponding simulator and delegates
    the location update to the underlying Bin model.
    """
    mock_simulator = MagicMock()
    mock_simulator.bin = bin_instance
    sim_manager._simulators["bin_1"] = mock_simulator
    
    sim_manager.update_bin("bin_1", 30.0, 40.0)
    
    assert mock_simulator.bin.latitude == 30.0
    assert mock_simulator.bin.longitude == 40.0

@pytest.mark.asyncio
async def test_stop_all(sim_manager):
    """
    Test the global stop function of the SimulationManager.
    Ensures that it halts all currently active simulators and clears its
    internal registry cleanly.
    """
    mock_sim1 = AsyncMock()
    mock_sim2 = AsyncMock()
    sim_manager._simulators["bin_1"] = mock_sim1
    sim_manager._simulators["bin_2"] = mock_sim2
    
    await sim_manager.stop()
    
    mock_sim1.stop.assert_called_once()
    mock_sim2.stop.assert_called_once()
    assert len(sim_manager._simulators) == 0
