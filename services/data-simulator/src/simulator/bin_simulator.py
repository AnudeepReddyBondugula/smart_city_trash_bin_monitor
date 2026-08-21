import asyncio
import logging
from random import uniform
from faker import Faker

from models.bin import Bin
from kafka_producer import kafka_client
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

fake = Faker()


class BinSimulator:
    """
    Simulates the lifecycle and telemetry generation of a single smart trash bin.

    This class owns a single :class:`Bin` instance and runs an asynchronous
    background task that periodically updates the bin's state and publishes
    telemetry to Kafka.

    Responsibilities:
        - Simulate fill level changes.
        - Simulate battery drain.
        - Generate telemetry payloads.
        - Publish telemetry at a fixed interval.
        - Manage the lifecycle of the simulation task.

    Attributes:
        bin (Bin):
            The smart bin being simulated.

        _running (bool):
            Indicates whether the simulator is currently running.

        _task (asyncio.Task | None):
            Background asyncio task responsible for periodic simulation and
            telemetry publishing.

    Notes:
        Each BinSimulator manages exactly one bin. Multiple simulators are
        coordinated by the SimulationManager.
    """

    def __init__(self, bin: Bin):
        """
        Initializes a simulator for the given bin.

        Args:
            bin:
                The bin to simulate.
        """
        logger.debug("Initializing simulator for bin '%s'.", bin.bin_id)

        self.bin = bin
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """
        Starts the telemetry simulation task.

        If the simulator is already running, the call is ignored.
        """
        if self._running:
            logger.warning(
                "Simulator is already running for bin '%s'.",
                self.bin.bin_id,
            )
            return

        self._running = True
        self._task = asyncio.create_task(self._run())

        logger.debug(
            "Started simulator for bin '%s'.",
            self.bin.bin_id,
        )

    async def stop(self) -> None:
        """
        Stops the simulator gracefully.

        Cancels the background task and waits for it to terminate before
        returning.
        """
        if not self._running:
            logger.warning(
                "Simulator for bin '%s' is already stopped.",
                self.bin.bin_id,
            )
            return

        logger.debug(
            "Stopping simulator for bin '%s'.",
            self.bin.bin_id,
        )

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                logger.warning(
                    "Simulation task cancelled for bin '%s'.",
                    self.bin.bin_id,
                )

        logger.debug(
            "Simulator stopped for bin '%s'.",
            self.bin.bin_id,
        )

    async def _run(self) -> None:
        """
        Executes the simulation loop.

        The loop periodically updates the bin state, generates a telemetry
        payload, publishes it to Kafka, and waits for the configured interval.
        """

        logger.debug(
            "Simulation loop started for bin '%s'.",
            self.bin.bin_id,
        )

        while self._running:
            self._simulate()
            logger.debug("Sending telemetry for %s", self.bin.bin_id)
            await kafka_client.send_telemetry(
                self.bin.bin_id,
                self.bin.to_payload(),
            )
            logger.debug("Telemetry sent for %s", self.bin.bin_id)

            await asyncio.sleep(
                settings.SIMULATION_INTERVAL,
            )

        logger.debug(
            "Simulation loop exited for bin '%s'.",
            self.bin.bin_id,
        )

    def _simulate(self) -> None:
        """
        Updates the simulated state of the bin.

        The simulation models:
            - Fill level changes
            - Battery consumption
            - Temperature drift
        """
        if fake.boolean(chance_of_getting_true=5):
            self.bin.current_fill_level = 0

            logger.debug(
                "Bin '%s' was emptied.",
                self.bin.bin_id,
            )

        else:
            increase = fake.pyfloat(
                min_value=0.5,
                max_value=5.0,
            )

            self.bin.current_fill_level = min(
                self.bin.capacity,
                self.bin.current_fill_level + increase,
            )

        self.bin.battery_level = max(
            0,
            self.bin.battery_level
            - fake.pyfloat(
                min_value=0.01,
                max_value=0.1,
            ),
        )

        self.bin.temperature = min(
            35.0,
            max(
                20.0,
                self.bin.temperature
                + uniform(-0.5, 0.5),
            ),
        )

        logger.debug(
            "Simulated bin '%s' | Fill: %.2f%% | Battery: %.2f%% | Temperature: %.2f C",
            self.bin.bin_id,
            self.bin.current_fill_level,
            self.bin.battery_level,
            self.bin.temperature,
        )
