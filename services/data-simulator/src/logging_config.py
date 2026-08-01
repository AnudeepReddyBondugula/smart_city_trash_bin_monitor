import logging
import signal
from pathlib import Path
from logging.handlers import RotatingFileHandler

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

    # Console
    console = colorlog.StreamHandler()
    console.setFormatter(color_formatter)

    # File
    file_handler = RotatingFileHandler(
        LOG_DIR / "simulator.log",
        maxBytes=20 * 1024 * 1024,  # 20 MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)

    # Suppress noisy library logs
    logging.getLogger("aiokafka.cluster").setLevel(logging.CRITICAL)

    # For enabling debugs on Runtime process
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
