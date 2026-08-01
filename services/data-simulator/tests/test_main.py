import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.main import main


@pytest.mark.asyncio
@patch("src.main.asyncio.Event")
@patch("src.main.engine")
@patch("src.main.SimulationManager")
@patch("src.main.kafka_client")
async def test_main_startup_and_clean_shutdown(
    mock_kafka_client,
    mock_simulation_manager_cls,
    mock_engine,
    mock_event_cls,
):
    """
    Test the happy-path startup and clean shutdown flow of main().
    Verifies the orchestration order: kafka start -> manager initialize ->
    (shutdown signal received) -> manager stop -> kafka stop -> engine dispose.
    """
    # Make stop_event.wait() resolve immediately so main() proceeds to cleanup.
    mock_stop_event = MagicMock()
    mock_stop_event.wait = AsyncMock()
    mock_event_cls.return_value = mock_stop_event

    mock_manager = AsyncMock()
    mock_simulation_manager_cls.return_value = mock_manager

    mock_kafka_client.start = AsyncMock()
    mock_kafka_client.stop = AsyncMock()
    mock_engine.dispose = AsyncMock()

    # Neutralize real signal-handler registration on the running loop so the
    # test process's SIGINT/SIGTERM handlers are not overwritten.
    loop = asyncio.get_running_loop()
    original_add_signal_handler = loop.add_signal_handler
    loop.add_signal_handler = MagicMock()
    try:
        await main()
    finally:
        loop.add_signal_handler = original_add_signal_handler

    # Startup sequence
    mock_kafka_client.start.assert_awaited_once()
    mock_simulation_manager_cls.assert_called_once()
    mock_manager.initialize.assert_awaited_once()

    # Cleanup sequence
    mock_manager.stop.assert_awaited_once()
    mock_kafka_client.stop.assert_awaited_once()
    mock_engine.dispose.assert_awaited_once()
