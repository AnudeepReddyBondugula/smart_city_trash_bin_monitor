import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.manager import SimulationManager
from src.database import SmartBin

@pytest.mark.asyncio
async def test_manager_sync_bins(test_session):
    manager = SimulationManager()
    
    # Mock AsyncSessionLocal to return our test_session
    class MockSessionManager:
        async def __aenter__(self):
            return test_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch('src.manager.AsyncSessionLocal', return_value=MockSessionManager()):
        # Insert a bin
        new_bin = SmartBin(bin_id="BIN-TEST-1", capacity=100.0, latitude=10.0, longitude=20.0, status="ACTIVE")
        test_session.add(new_bin)
        await test_session.commit()
        
        # Sync
        await manager._sync_bins()
        
        assert "BIN-TEST-1" in manager.simulators
        assert manager.simulators["BIN-TEST-1"].bin_id == "BIN-TEST-1"
        
        # Change status to maintenance
        new_bin.status = "MAINTENANCE"
        await test_session.commit()
        
        # Sync
        await manager._sync_bins()
        assert "BIN-TEST-1" not in manager.simulators
        
        # Clean up tasks
        await manager.stop()
