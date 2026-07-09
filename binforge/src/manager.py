import asyncio
import logging
from sqlalchemy.future import select
from .database import AsyncSessionLocal, SmartBin
from .simulator import BinSimulator
from .config import settings
from .kafka_producer import kafka_client

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self):
        self.simulators = {}  # bin_id -> BinSimulator
        self._running = False
        self._poll_task = None
        self._telemetry_task = None

    def start(self):
        if not self._running:
            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
            logger.info("Simulation Manager started")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
        if self._telemetry_task:
            self._telemetry_task.cancel()
            
        try:
            if self._poll_task: await self._poll_task
            if self._telemetry_task: await self._telemetry_task
        except asyncio.CancelledError:
            pass
            
        self.simulators.clear()
        logger.info("Simulation Manager stopped")

    async def _poll_loop(self):
        try:
            while self._running:
                await self._sync_bins()
                await asyncio.sleep(settings.DB_POLL_INTERVAL_SEC)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Simulation manager poll loop error: {e}")
            self._running = False

    async def _telemetry_loop(self):
        try:
            while self._running:
                if self.simulators:
                    tasks = []
                    for sim in self.simulators.values():
                        payload = sim.generate_payload()
                        tasks.append(kafka_client.send_telemetry(sim.bin_id, payload))
                    
                    # Fire all telemetry to Kafka concurrently
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Log any errors from the gather
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(f"Error sending telemetry in batch loop: {result}")
                            
                await asyncio.sleep(settings.TELEMETRY_INTERVAL_SEC)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Simulation manager telemetry loop error: {e}")
            self._running = False

    async def _sync_bins(self):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(SmartBin).where(SmartBin.status == 'ACTIVE'))
                active_bins = result.scalars().all()
                
                active_bin_ids = {b.bin_id for b in active_bins}
                
                # Start or update simulators
                for b in active_bins:
                    if b.bin_id not in self.simulators:
                        sim = BinSimulator(b.bin_id, b.capacity, b.latitude, b.longitude)
                        self.simulators[b.bin_id] = sim
                    else:
                        sim = self.simulators[b.bin_id]
                        if sim.latitude != b.latitude or sim.longitude != b.longitude:
                            sim.update_location(b.latitude, b.longitude)
                
                # Remove simulators for bins that are no longer active
                current_sim_ids = list(self.simulators.keys())
                for sid in current_sim_ids:
                    if sid not in active_bin_ids:
                        del self.simulators[sid]
                        
        except Exception as e:
            logger.error(f"Error syncing bins from database: {e}")
