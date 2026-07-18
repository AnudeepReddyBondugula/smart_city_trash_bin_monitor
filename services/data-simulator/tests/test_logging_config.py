import logging
import signal
import pytest
from src.logging_config import setup_logging, _toggle_log_level

@pytest.fixture(autouse=True)
def reset_logger():
    """Backup and restore root logger state before and after each test."""
    root_logger = logging.getLogger()
    old_handlers = list(root_logger.handlers)
    old_level = root_logger.level
    
    yield
    
    root_logger.handlers.clear()
    for handler in old_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(old_level)

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

def test_signal_handler_integration():
    """
    Test that sending a SIGUSR1 signal to the process actually triggers 
    the log level toggle via the registered signal handler.
    """
    import os
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # setup_logging registers the signal handler
    setup_logging("INFO")
    assert root_logger.level == logging.INFO
    
    # Send SIGUSR1 to our own test process (simulating `kill -USR1 <pid>`)
    os.kill(os.getpid(), signal.SIGUSR1)
    
    # The signal handler should change the level to DEBUG
    assert root_logger.level == logging.DEBUG
    
    # Send SIGUSR1 again to toggle back to INFO
    os.kill(os.getpid(), signal.SIGUSR1)
    assert root_logger.level == logging.INFO
