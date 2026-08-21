from models.bin import Bin
from simulator.bin_simulator import BinSimulator, assign_fault_modes

from database import AsyncSessionLocal, SmartBin, engine
from sqlalchemy import inspect, select

import logging

logger = logging.getLogger(__name__)


class SchemaNotReadyError(RuntimeError):
    """The database has not been migrated yet.

    Raised instead of letting the driver's own error escape. A missing table
    surfaces from asyncpg as a thirty-line traceback with the one useful line
    at the bottom, which tells an operator nothing about what to do next -
    and migrations are deliberately a manual step here, so this is an ordinary
    thing to get wrong rather than an exceptional one.
    """


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

    async def require_schema(self) -> None:
        """
        Check the bins table exists before anything tries to read it.

        Migrations are a deliberate manual step, so starting against an
        unmigrated database is a routine mistake rather than an exceptional
        one, and deserves an answer rather than a stack trace.

        Raises:
            SchemaNotReadyError:
                The table is missing, with the command that creates it.
        """
        async with engine.connect() as connection:
            has_table = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).has_table(
                    SmartBin.__tablename__
                )
            )

        if not has_table:
            raise SchemaNotReadyError(
                f"The '{SmartBin.__tablename__}' table does not exist. "
                "Migrations are a manual step; run them before starting the "
                "simulator:\n"
                "    docker compose run --rm data_simulator alembic upgrade head\n"
                "    docker compose run --rm data_simulator python src/seed.py --count 200"
            )

    async def initialize(self) -> None:
        """
        Loads all bins from the database and starts their simulators.

        Raises:
            SchemaNotReadyError:
                The database has not been migrated.
        """
        await self.require_schema()

        logger.info("Loading bins from database...")

        async with AsyncSessionLocal() as session:

            # Fetching only ACTIVE bins for emiting the telemtry data
            result = await session.execute(
                select(SmartBin).where(SmartBin.status == "ACTIVE")
            )
            db_bins = result.scalars().all()

            bins = [
                Bin(
                    bin_id=db_bin.bin_id,
                    latitude=db_bin.latitude,
                    longitude=db_bin.longitude,
                    capacity=db_bin.capacity,
                    zone=db_bin.zone,
                )
                for db_bin in db_bins
            ]

            # Faults are assigned across the whole fleet at once rather than per
            # bin, so the share of faulty bins and the spread of fault modes are
            # both known rather than left to chance.
            assign_fault_modes(bins)

            for bin in bins:
                simulator = BinSimulator(bin)
                simulator.start()

                self._simulators[bin.bin_id] = simulator

        if not self._simulators:
            # Not fatal - bins can be added later - but silence here reads as a
            # broken simulator when it is really an unseeded database.
            logger.warning(
                "No ACTIVE bins found, so nothing will be published. Seed the "
                "database:\n"
                "    docker compose run --rm data_simulator python src/seed.py "
                "--count 200"
            )
            return

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
