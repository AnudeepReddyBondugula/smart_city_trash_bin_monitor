import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.create_tables import create_tables, main


@pytest.mark.asyncio
@patch("src.create_tables.Base")
@patch("src.create_tables.engine")
async def test_create_tables_invokes_create_all(mock_engine, mock_base):
    """
    Test that create_tables opens a transaction and runs
    Base.metadata.create_all via run_sync, then disposes the engine.
    """
    mock_conn = MagicMock()
    mock_conn.run_sync = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.dispose = AsyncMock()

    await create_tables()

    mock_conn.run_sync.assert_awaited_once_with(mock_base.metadata.create_all)
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.create_tables.Base")
@patch("src.create_tables.engine")
async def test_create_tables_main_disposes_engine(mock_engine, mock_base):
    """
    Test that main() invokes the real create_tables() and disposes the engine
    via its finally block. Because create_tables() ALSO disposes the engine
    internally (src/create_tables.py:15), a correct run through main() must
    dispose exactly twice. Patching create_tables away would hide this
    duplicate-dispose path, so we exercise the real implementation.
    """
    mock_conn = MagicMock()
    mock_conn.run_sync = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_engine.dispose = AsyncMock()

    await main()

    # create_tables() actually ran
    mock_conn.run_sync.assert_awaited_once_with(mock_base.metadata.create_all)
    # create_tables() disposes once, then main()'s finally disposes again
    assert mock_engine.dispose.await_count == 2
