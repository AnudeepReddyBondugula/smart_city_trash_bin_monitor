import asyncio
import logging
import signal
from src.kafka_producer import kafka_client
from src.manager import SimulationManager
from src.database import engine
import sys

import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# Suppress harmless "Topic not found" error during auto-creation
logging.getLogger("aiokafka.cluster").setLevel(logging.CRITICAL)

async def main():
    logger.info("Starting BinForge Simulator")
    
    # Start Kafka Producer
    await kafka_client.start()
    
    # Start Manager
    manager = SimulationManager()
    manager.start()

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
    
    # Cleanup with timeout
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
        
    logger.info("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
