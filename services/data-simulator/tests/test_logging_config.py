import logging
import signal
from unittest.mock import patch

import pytest
from src.logging_config import setup_logging, _toggle_log_level

@pytest.fixture(autouse=True)
def reset_logger():
    """Backup and restore root logger state AND the SIGUSR1 signal handler
    so that setup_logging's process-wide signal registration cannot leak
    across tests."""
    root_logger = logging.getLogger()
    old_handlers = list(root_logger.handlers)
    old_level = root_logger.level
    old_sigusr1_handler = signal.getsignal(signal.SIGUSR1)

    yield

    root_logger.handlers.clear()
    for handler in old_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(old_level)
    signal.signal(signal.SIGUSR1, old_sigusr1_handler)

def test_setup_logging_initialization():
    """
    Test that the setup_logging function properly initializes the root logger.
    It should set the correct logging level (INFO by default) and attach exactly 
    two handlers (console and rotating file handler).
    """
    root_logger = logging.getLogger()
    # clear handlers for a clean slate
    root_logger.handlers.clear()
    
    logger = setup_logging("INFO")
    
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 2
    
def test_setup_logging_prevents_duplicates():
    """
    Test that calling setup_logging multiple times does not add duplicate
    handlers to the root logger, ensuring idempotent behavior.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    setup_logging("INFO")
    assert len(root_logger.handlers) == 2
    
    setup_logging("INFO")
    assert len(root_logger.handlers) == 2

def test_setup_logging_custom_level_debug():
    """
    Test that setup_logging accepts a custom level name (DEBUG) and applies it.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    setup_logging("DEBUG")

    assert root_logger.level == logging.DEBUG

def test_setup_logging_custom_level_warning():
    """
    Test that setup_logging accepts a custom level name (WARNING) and applies it.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    setup_logging("WARNING")

    assert root_logger.level == logging.WARNING

def test_setup_logging_invalid_level_falls_back_to_info():
    """
    Test that an unrecognized level string falls back to INFO rather than raising.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    setup_logging("NOT_A_REAL_LEVEL")

    assert root_logger.level == logging.INFO

def test_toggle_log_level_function():
    """
    Test that the _toggle_log_level function successfully switches the root 
    logger's level between INFO and DEBUG.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    _toggle_log_level(signal.SIGUSR1, None)
    assert root_logger.level == logging.DEBUG
    
    _toggle_log_level(signal.SIGUSR1, None)
    assert root_logger.level == logging.INFO

def test_setup_logging_registers_sigusr1_handler():
    """
    Test that setup_logging registers the SIGUSR1 signal handler used for
    runtime log-level toggling. Verifies registration via signal.signal rather
    than delivering a real signal to the pytest process (which is brittle and
    platform-dependent). The handler's behavior is covered separately by
    test_toggle_log_level_function.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    with patch("src.logging_config.signal.signal") as mock_signal_signal:
        setup_logging("INFO")

        sigusr1_calls = [
            call
            for call in mock_signal_signal.call_args_list
            if call.args and call.args[0] == signal.SIGUSR1
        ]
        assert len(sigusr1_calls) == 1
        # The registered handler must be the module's toggle function
        assert sigusr1_calls[0].args[1] is _toggle_log_level
