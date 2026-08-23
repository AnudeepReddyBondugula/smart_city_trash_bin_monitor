import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.main import main

# NOTE: import SchemaNotReadyError the same way main.py does
# (`from simulator.simulation_manager import ...`). Because `src/` has no
# __init__.py, `simulator.simulation_manager.SchemaNotReadyError` and
# `src.simulator.simulation_manager.SchemaNotReadyError` are two distinct class
# objects, and an `except` against the wrong one never matches.
from simulator.simulation_manager import SchemaNotReadyError


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


@pytest.mark.asyncio
@patch("src.main.engine")
@patch("src.main.SimulationManager")
@patch("src.main.kafka_client")
async def test_failed_startup_still_releases_the_kafka_producer(
    mock_kafka_client,
    mock_simulation_manager_cls,
    mock_engine,
):
    """Cleanup runs even when startup fails.

    The cleanup block used to sit after the shutdown wait, which never happens
    if startup raises. A crash therefore left the producer open and the process
    died complaining about an unclosed AIOKafkaProducer - burying the real
    cause under a warning about a symptom.
    """
    mock_manager = AsyncMock()
    mock_manager.initialize.side_effect = SchemaNotReadyError("run alembic")
    mock_simulation_manager_cls.return_value = mock_manager

    mock_kafka_client.start = AsyncMock()
    mock_kafka_client.stop = AsyncMock()
    mock_engine.dispose = AsyncMock()

    exit_code = await main()

    mock_kafka_client.stop.assert_awaited_once()
    mock_engine.dispose.assert_awaited_once()
    assert exit_code == 1


@pytest.mark.asyncio
@patch("src.main.engine")
@patch("src.main.SimulationManager")
@patch("src.main.kafka_client")
async def test_missing_schema_is_reported_without_a_traceback(
    mock_kafka_client,
    mock_simulation_manager_cls,
    mock_engine,
    caplog,
):
    """The operator is told what to run, not shown a stack trace."""
    mock_manager = AsyncMock()
    mock_manager.initialize.side_effect = SchemaNotReadyError(
        "The 'smart_bins' table does not exist. Run: alembic upgrade head"
    )
    mock_simulation_manager_cls.return_value = mock_manager

    mock_kafka_client.start = AsyncMock()
    mock_kafka_client.stop = AsyncMock()
    mock_engine.dispose = AsyncMock()

    exit_code = await main()

    assert exit_code == 1
    assert "alembic upgrade head" in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.asyncio
@patch("src.main.engine")
@patch("src.main.kafka_client")
async def test_shutdown_continues_after_a_failing_step(mock_kafka_client, mock_engine):
    """One failing step must not skip the ones after it.

    A producer left open because the manager stopped badly is a leak the logs
    would then blame on the wrong component.
    """
    from src.main import shutdown

    manager = AsyncMock()
    manager.stop.side_effect = RuntimeError("manager is wedged")
    mock_kafka_client.stop = AsyncMock()
    mock_engine.dispose = AsyncMock()

    await shutdown(manager)

    mock_kafka_client.stop.assert_awaited_once()
    mock_engine.dispose.assert_awaited_once()
