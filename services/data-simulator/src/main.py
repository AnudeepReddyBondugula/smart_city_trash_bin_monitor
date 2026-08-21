import asyncio
import signal
from kafka_producer import kafka_client
from simulator.simulation_manager import SchemaNotReadyError, SimulationManager
from database import engine
import sys

import logging
from logging_config import setup_logging

# Configure logging ONCE
setup_logging()

logger = logging.getLogger(__name__)


async def shutdown(manager):
    """
    Release everything the process holds, in order, tolerating failures.

    Each step is guarded so one failure cannot skip the ones after it - a
    producer left open because the manager stopped badly is a resource leak the
    logs would then blame on the wrong thing.
    """
    if manager is not None:
        try:
            await asyncio.wait_for(manager.stop(), timeout=5.0)
        except Exception as e:
            logger.warning(f"Manager stop timed out or failed: {e}")

    try:
        await asyncio.wait_for(kafka_client.stop(), timeout=5.0)
    except Exception as e:
        logger.warning(f"Kafka client stop timed out or failed: {e}")

    try:
        await engine.dispose()
    except Exception as e:
        logger.warning(f"Engine disposal failed: {e}")


async def main():
    logger.info("Initializing Data Simulator")

    manager = None

    # Start Kafka Producer
    logger.info("Initializing Kafka Client")

    await kafka_client.start()

    logger.info("Kafka Client Started Successfully")

    # Everything past this point runs with the producer open, so cleanup has to
    # happen on the way out whether startup succeeded or not. It previously sat
    # after the shutdown wait, so a failure to start left the Kafka producer
    # open and the process died complaining about it instead of about the
    # actual problem.
    try:
        # Start Manager
        logger.info("Initializing Simulation Manager")
        manager = SimulationManager()
        await manager.initialize()

        logger.info("Simulation Manager Started Successfully")

        # Handle graceful shutdown
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def handle_shutdown(*args):
            logger.info("Shutdown signal received")
            loop.call_soon_threadsafe(stop_event.set)

        if sys.platform == "win32":
            # Windows does not support loop.add_signal_handler
            signal.signal(signal.SIGINT, handle_shutdown)
            signal.signal(signal.SIGTERM, handle_shutdown)
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: handle_shutdown())

        await stop_event.wait()

    except SchemaNotReadyError as error:
        # An operator forgot a documented step. Report what to do and stop -
        # a traceback here only buries the instruction.
        logger.error("%s", error)
        return 1

    finally:
        await shutdown(manager)
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
