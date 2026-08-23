"""Logging setup, matching the data-simulator's so both services read alike."""

import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorlog

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger()

    # Prevent duplicate handlers
    if root.handlers:
        return root

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    color_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )

    console = colorlog.StreamHandler()
    console.setFormatter(color_formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "stream-processor.log",
        maxBytes=20 * 1024 * 1024,  # 20 MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)

    # py4j logs every gateway call at INFO, which buries everything else.
    logging.getLogger("py4j").setLevel(logging.WARNING)

    # For enabling debugs on a running process
    signal.signal(signal.SIGUSR1, _toggle_log_level)

    return root


def _toggle_log_level(signum, frame):
    root = logging.getLogger()

    if root.level == logging.INFO:
        root.setLevel(logging.DEBUG)
    else:
        root.setLevel(logging.INFO)

    root.info(
        "Runtime log level changed to %s",
        logging.getLevelName(root.level),
    )
