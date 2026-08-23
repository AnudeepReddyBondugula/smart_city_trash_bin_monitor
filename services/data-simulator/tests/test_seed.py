import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.seed import (
    BIN_CAPACITIES,
    HYDERABAD_CENTER,
    MAX_BINS_PER_RUN,
    ZONE_OFFSETS,
    seed_db,
)

# NOTE: import SmartBin the same way seed.py does (`from database import ...`).
# Because `src/` has no __init__.py, `database.SmartBin` and `src.database.SmartBin`
# resolve to two distinct class objects; matching seed.py's import keeps
# isinstance / call-arg checks correct.
from database import SmartBin


def _build_session_mock():
    """
    Build a mock AsyncSession with explicit sync/async method separation:
      - session.add(...) is a sync MagicMock (matches SQLAlchemy's sync API).
      - session.execute(...) / session.commit(...) are AsyncMocks.
    """
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    return mock_session


def _wire_session_factory(mock_async_sessionmaker, mock_session):
    """Configure `async_sessionmaker(...)` so `async with AsyncSessionLocal() as s` yields mock_session."""
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session_factory.return_value.__aexit__.return_value = None
    mock_async_sessionmaker.return_value = mock_session_factory


@pytest.mark.asyncio
@patch("src.seed.async_sessionmaker")
@patch("src.seed.create_async_engine")
async def test_seed_creates_bins_and_commits(mock_create_engine, mock_async_sessionmaker):
    """
    Test that seed_db creates the requested number of bins and commits.
    Verifies session.add is called `count` times and commit is awaited.
    """
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    mock_session = _build_session_mock()
    _wire_session_factory(mock_async_sessionmaker, mock_session)

    await seed_db(count=3, clear=False)

    assert mock_session.add.call_count == 3
    # All added objects are SmartBin instances
    for call_args in mock_session.add.call_args_list:
        bin_instance = call_args.args[0]
        assert isinstance(bin_instance, SmartBin)
        assert bin_instance.zone in ZONE_OFFSETS
        latitude_offset, longitude_offset = ZONE_OFFSETS[bin_instance.zone]
        assert HYDERABAD_CENTER[0] + latitude_offset[0] <= bin_instance.latitude
        assert bin_instance.latitude <= HYDERABAD_CENTER[0] + latitude_offset[1]
        assert HYDERABAD_CENTER[1] + longitude_offset[0] <= bin_instance.longitude
        assert bin_instance.longitude <= HYDERABAD_CENTER[1] + longitude_offset[1]
    mock_session.commit.assert_awaited()
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.seed.async_sessionmaker")
@patch("src.seed.create_async_engine")
@patch("src.seed.delete")
async def test_seed_clear_true_deletes_first(
    mock_delete, mock_create_engine, mock_async_sessionmaker
):
    """
    Test that when clear=True, existing bins are deleted and committed before
    new bins are added. Verifies the delete(SmartBin) statement is issued and
    that commit is awaited twice (once for clear, once for adds).
    """
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    mock_session = _build_session_mock()
    _wire_session_factory(mock_async_sessionmaker, mock_session)

    await seed_db(count=2, clear=True)

    # delete(SmartBin) was passed to session.execute
    mock_delete.assert_called_once_with(SmartBin)
    mock_session.execute.assert_awaited_once()
    # Two commits: one after clearing, one after adding the new bins
    assert mock_session.commit.await_count == 2
    assert mock_session.add.call_count == 2


@pytest.mark.asyncio
@patch("src.seed.create_async_engine")
async def test_seed_over_the_cap_is_rejected(mock_create_engine, capsys):
    """
    Test the safety guard: requesting more bins than the cap allows is rejected
    early, prints an error, and never creates a database engine nor session.
    """
    await seed_db(count=MAX_BINS_PER_RUN + 1, clear=False)

    captured = capsys.readouterr()
    assert f"cannot seed more than {MAX_BINS_PER_RUN}" in captured.out.lower()
    mock_create_engine.assert_not_called()


@pytest.mark.asyncio
@patch("src.seed.async_sessionmaker")
@patch("src.seed.create_async_engine")
async def test_seed_uses_a_range_of_capacities(
    mock_create_engine, mock_async_sessionmaker
):
    """
    Test that seeded bins are not all the same size.
    A single capacity would make the raw fill level and the fill percentage
    numerically identical, hiding every percentage threshold downstream.
    """
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    mock_session = _build_session_mock()
    _wire_session_factory(mock_async_sessionmaker, mock_session)

    await seed_db(count=200, clear=False)

    capacities = {
        call_args.args[0].capacity for call_args in mock_session.add.call_args_list
    }
    assert capacities <= set(BIN_CAPACITIES)
    assert len(capacities) > 1


@pytest.mark.asyncio
@patch("src.seed.async_sessionmaker")
@patch("src.seed.create_async_engine")
async def test_seed_exception_disposes_engine(
    mock_create_engine, mock_async_sessionmaker, capsys
):
    """
    Test that engine.dispose() is always invoked in the finally block, even
    when an exception occurs during seeding (exception is caught internally).
    """
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    mock_session = _build_session_mock()
    # Simulate a failure on the final commit
    mock_session.commit.side_effect = Exception("DB connection lost")
    _wire_session_factory(mock_async_sessionmaker, mock_session)

    # Should NOT raise: seed_db catches exceptions internally
    await seed_db(count=2, clear=False)

    captured = capsys.readouterr()
    assert "An error occurred while seeding" in captured.out
    mock_engine.dispose.assert_awaited_once()
