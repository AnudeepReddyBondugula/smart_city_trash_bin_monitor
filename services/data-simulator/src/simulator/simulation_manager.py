from models.bin import Bin
from simulator.bin_simulator import BinSimulator

from database import AsyncSessionLocal, SmartBin
from sqlalchemy import select

import logging

logger = logging.getLogger(__name__)


class SimulationManager:
    """
    Manages the lifecycle of all active bin simulators.

    The SimulationManager acts as an in-memory registry for
    :class:`BinSimulator` instances. It is responsible for creating,
    updating, and removing simulators as bins are added, updated,
    or deleted.

    Attributes:
        _simulators (dict[str, BinSimulator]):
            Mapping of bin IDs to their corresponding simulator.
    """

    def __init__(self):
        """
        Initializes an empty simulation manager.
        """
        logger.info("Initializing SimulationManager.")

        self._simulators: dict[str, BinSimulator] = {}

    async def initialize(self) -> None:
        """
        Loads all bins from the database and starts their simulators.
        """
        logger.info("Loading bins from database...")

        async with AsyncSessionLocal() as session:

            # Fetching only ACTIVE bins for emiting the telemtry data
            result = await session.execute(
                select(SmartBin).where(SmartBin.status == "ACTIVE")
            )
            db_bins = result.scalars().all()

            for db_bin in db_bins:

                bin = Bin(
                    bin_id=db_bin.bin_id,
                    latitude=db_bin.latitude,
                    longitude=db_bin.longitude,
                    capacity=db_bin.capacity,
                    zone=db_bin.zone,
                )

                simulator = BinSimulator(bin)
                simulator.start()

                self._simulators[bin.bin_id] = simulator

        logger.info(
            "Started %d simulator(s).",
            len(self._simulators),
        )

    #! Add, update, delete - need to be implemented with Fast API in future involving DB interaction
    def add_bin(self, bin: Bin) -> None:
        """
        Creates and starts a simulator for a new bin.

        Args:
            bin:
                The bin to simulate.
        """
        if bin.bin_id in self._simulators:
            logger.warning(
                "Simulator already exists for bin '%s'.",
                bin.bin_id,
            )
            return

        simulator = BinSimulator(bin)
        simulator.start()

        self._simulators[bin.bin_id] = simulator

        logger.info(
            "Added simulator for bin '%s'.",
            bin.bin_id,
        )

    async def remove_bin(self, bin_id: str) -> None:
        """
        Stops and removes the simulator associated with a bin.

        Args:
            bin_id:
                Unique identifier of the bin.
        """
        simulator = self._simulators.pop(bin_id, None)

        if simulator is None:
            logger.warning(
                "No simulator found for bin '%s'.",
                bin_id,
            )
            return

        await simulator.stop()

        logger.info(
            "Removed simulator for bin '%s'.",
            bin_id,
        )

    def update_bin(
        self,
        bin_id: str,
        latitude: float,
        longitude: float,
    ) -> None:
        """
        Updates the location of an existing simulated bin.

        Args:
            bin_id:
                Unique identifier of the bin.

            latitude:
                Updated latitude.

            longitude:
                Updated longitude.
        """
        simulator = self._simulators.get(bin_id)

        if simulator is None:
            logger.warning(
                "No simulator found for bin '%s'.",
                bin_id,
            )
            return

        simulator.bin.update_location(
            latitude=latitude,
            longitude=longitude,
        )

        logger.info(
            "Updated location for bin '%s'.",
            bin_id,
        )

    async def stop(self) -> None:
        """
        Stops all active simulators and clears the registry.
        """
        logger.info(
            "Stopping %d simulator(s).",
            len(self._simulators),
        )

        for simulator in list(self._simulators.values()):
            await simulator.stop()

        self._simulators.clear()

        logger.info("All simulators stopped.")

    def get_simulator(
        self,
        bin_id: str,
    ) -> BinSimulator | None:
        """
        Returns the simulator for the given bin.

        Args:
            bin_id:
                Unique identifier of the bin.

        Returns:
            The corresponding BinSimulator if found, otherwise None.
        """
        return self._simulators.get(bin_id)

    def exists(self, bin_id: str) -> bool:
        """
        Checks whether a simulator exists for the given bin.

        Args:
            bin_id:
                Unique identifier of the bin.

        Returns:
            True if the simulator exists, otherwise False.
        """
        return bin_id in self._simulators

    @property
    def simulators(self) -> dict[str, BinSimulator]:
        """
        Returns all active simulators.

        Returns:
            Dictionary of active simulators keyed by bin ID.
        """
        return self._simulators
