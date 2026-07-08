import asyncio
import logging
import signal
from src.kafka_producer import kafka_client
from src.manager import SimulationManager
from src.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

    def handle_shutdown():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_shutdown)
        except NotImplementedError:
            pass # add_signal_handler not implemented on Windows

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
