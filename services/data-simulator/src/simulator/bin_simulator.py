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

# The ways a bin is allowed to misbehave.
#
# Every one of these exists to give a downstream detector something to detect.
# A simulation in which nothing ever goes wrong can only demonstrate the happy
# path, so the offline, stuck-sensor, duplicate, impossible-value, fire-risk and
# abnormal-jump rules would all be written and never once observed firing.
#
#   SILENT       stops publishing         -> dead device detection
#   FROZEN       republishes one reading  -> stuck sensor detection
#   SPIKE        reports values no sensor could produce -> sensor fault, dead letters
#   DUPLICATE    re-sends the last event verbatim -> deduplication
#   HOT          runs far above ambient   -> fire risk detection
#   JUMP         one large but legal fill jump -> abnormal jump detection
#   UNCOLLECTED  is never emptied         -> SLA breach detection
FAULT_MODES = (
    "SILENT",
    "FROZEN",
    "SPIKE",
    "DUPLICATE",
    "HOT",
    "JUMP",
    "UNCOLLECTED",
)

# A temperature no real sensor reports, used by the SPIKE fault. This sits
# outside the range the telemetry contract declares valid, so consumers reject
# it, which is the point - unlike a HOT bin, which is extreme but believable.
IMPOSSIBLE_TEMPERATURE = 150.0


def assign_fault_modes(bins: list[Bin], rate: float | None = None) -> None:
    """
    Mark a share of bins as faulty, cycling through the fault modes.

    Assignment is deliberately deterministic rather than a random draw per bin.
    Drawing independently means a small fleet can easily end up with no HOT bin
    and therefore no fire-risk alert anywhere in the run, which looks identical
    to a broken detector. Cycling guarantees that once at least
    ``len(FAULT_MODES)`` bins are marked, every mode is represented exactly.

    Args:
        bins:
            The bins to mark, modified in place.

        rate:
            Fraction of bins to make faulty. Defaults to the configured
            ``FAULT_INJECTION_RATE``. Zero disables fault injection entirely.
    """
    if rate is None:
        rate = settings.FAULT_INJECTION_RATE

    faulty_count = int(len(bins) * rate)

    for index in range(faulty_count):
        bins[index].fault_mode = FAULT_MODES[index % len(FAULT_MODES)]

    if faulty_count:
        logger.info(
            "Injected faults into %d of %d bin(s).",
            faulty_count,
            len(bins),
        )


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

        # Retained so the DUPLICATE fault can re-send a previous event exactly
        # as it went out the first time. Deduplication downstream keys on
        # (bin_id, timestamp), so a "duplicate" carrying a fresh timestamp is
        # not a duplicate at all and would silently pass straight through.
        self._last_payload: dict | None = None

        # How many readings this bin has published, used by the SILENT fault to
        # report for a while before dying.
        self._published = 0

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
                # Debug, not warning: cancelling the task is how stop() works,
                # so this is the expected path. At warning level an ordinary
                # shutdown buried the log under one line per bin - which trains
                # everyone to ignore warnings from this service.
                logger.debug(
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

            payload = self._next_payload()

            if payload is not None:
                logger.debug("Sending telemetry for %s", self.bin.bin_id)
                await kafka_client.send_telemetry(
                    self.bin.bin_id,
                    payload,
                )
                logger.debug("Telemetry sent for %s", self.bin.bin_id)

            await asyncio.sleep(
                settings.SIMULATION_INTERVAL,
            )

        logger.debug(
            "Simulation loop exited for bin '%s'.",
            self.bin.bin_id,
        )

    def _next_payload(self) -> dict | None:
        """
        Build the payload to publish this tick, or None to publish nothing.

        This is where the two faults that are about *publishing* rather than
        about bin state are applied. Everything else is handled in
        :meth:`_simulate`.

        Returns:
            The telemetry payload, or None if this bin is currently silent.
        """
        # A silent bin reports for a while and then dies, rather than never
        # reporting at all. Dead-device detection arms a timer when a bin
        # reports and raises the alert when that timer expires, so a bin that
        # has never once been heard from cannot be reported as lost - nothing
        # downstream knows it exists.
        if self.bin.fault_mode == "SILENT":
            if self._published >= settings.SILENCE_AFTER_READINGS:
                logger.debug(
                    "Bin '%s' has gone silent; publishing nothing.",
                    self.bin.bin_id,
                )
                return None

        # Re-send the previous event byte for byte, original timestamp included.
        # Alternating means a duplicate is always followed by a fresh reading,
        # so the bin still makes progress instead of stalling on one event.
        if self.bin.fault_mode == "DUPLICATE" and self._last_payload is not None:
            duplicate = self._last_payload
            self._last_payload = None

            logger.debug(
                "Bin '%s' is re-sending its previous event.",
                self.bin.bin_id,
            )
            self._published += 1
            return duplicate

        payload = self.bin.to_payload()

        if self.bin.fault_mode == "SPIKE":
            payload = self._corrupt(payload)

        self._last_payload = payload
        self._published += 1
        return self._last_payload

    def _corrupt(self, payload: dict) -> dict:
        """
        Report a value no sensor could produce, leaving the bin itself alone.

        A broken sensor is a fault in what is *reported*, not in what is true,
        so this corrupts the outgoing payload rather than the bin's state. The
        bin carries on filling normally underneath, which is what makes it
        worth still tracking.

        Alternates between two kinds of nonsense, because consumers treat them
        differently and both paths need exercising: an impossible temperature
        says nothing about how full the bin is and can be discarded on its own,
        while an impossible fill level leaves nothing usable in the message.
        """
        corrupted = dict(payload)

        if self._published % 2 == 0:
            corrupted["temperature"] = IMPOSSIBLE_TEMPERATURE
        else:
            corrupted["current_fill_level"] = round(self.bin.capacity * 1.5, 2)

        return corrupted

    def _simulate(self) -> None:
        """
        Updates the simulated state of the bin.

        The simulation models:
            - Fill level changes, including collection
            - Battery consumption
            - Temperature drift

        A bin with the FROZEN fault is skipped entirely, so it keeps reporting
        the reading it was last on. The remaining state-level faults are applied
        by the individual steps below.
        """
        if self.bin.fault_mode == "FROZEN":
            logger.debug(
                "Bin '%s' is frozen on its last reading.",
                self.bin.bin_id,
            )
            return

        self._simulate_fill()
        self._simulate_battery()
        self._simulate_temperature()

        logger.debug(
            "Simulated bin '%s' | Fill: %.2f%% | Battery: %.2f%% | Temperature: %.2f C",
            self.bin.bin_id,
            self.bin.fill_pct,
            self.bin.battery_level,
            self.bin.temperature,
        )

    def _simulate_fill(self) -> None:
        """
        Advances the fill level, emptying the bin if it is collected.

        A bin is only ever collected once it is actually worth collecting.
        Emptying at any fill level, as this previously did, has two problems: a
        bin is emptied so often that it never reaches a critical level at a
        realistic fill rate, and a drop from a low level is not something
        downstream collection detection recognises, so it registers as neither a
        collection nor anything else.
        """
        # An UNCOLLECTED bin is one the truck never comes for. It is the only
        # way an SLA clock is ever allowed to run out: every other bin is
        # emptied long inside the two hours the rules allow, so without this
        # fault the SLA breach rule could never be observed firing.
        collectable = (
            self.bin.fill_pct >= settings.COLLECTION_THRESHOLD_PCT
            and self.bin.fault_mode != "UNCOLLECTED"
        )

        if collectable and fake.boolean(
            chance_of_getting_true=settings.COLLECTION_CHANCE_PCT
        ):
            self.bin.current_fill_level = 0

            logger.debug(
                "Bin '%s' was emptied.",
                self.bin.bin_id,
            )
            return

        # Scaled by capacity so bins of every size cross the percentage
        # thresholds downstream at the same pace.
        increase = (
            self.bin.capacity
            * fake.pyfloat(
                min_value=settings.FILL_RATE_PCT_MIN,
                max_value=settings.FILL_RATE_PCT_MAX,
            )
            / 100
        )

        # A jump large enough to look wrong, but still a level the bin could
        # legitimately hold - so it passes validation and has to be caught by
        # comparing against the previous reading rather than by a range check.
        if self.bin.fault_mode == "JUMP":
            increase = self.bin.capacity * 0.4

        self.bin.current_fill_level = min(
            self.bin.capacity,
            self.bin.current_fill_level + increase,
        )

    def _simulate_battery(self) -> None:
        """
        Drains the battery, which never goes below zero.
        """
        self.bin.battery_level = max(
            0,
            self.bin.battery_level
            - fake.pyfloat(
                min_value=settings.BATTERY_DRAIN_MIN,
                max_value=settings.BATTERY_DRAIN_MAX,
            ),
        )

    def _simulate_temperature(self) -> None:
        """
        Updates the temperature.

        A healthy bin drifts within the ambient band. The two faults leave it
        deliberately:

        SPIKE reports a value no sensor could produce, which consumers reject
        outright.

        HOT reports a real but dangerous temperature, scaled by how full the bin
        is. Fire risk means hot *and* nearly full together, so a bin that simply
        pinned itself to a high temperature from empty would satisfy one half of
        that rule forever and the other half never, and the alert would still
        not fire. Scaling with fill level means the bin crosses the 70 C fire
        threshold at around 64% full and is well past it by the time it is full
        enough to matter - and it does so at any capacity and any fill rate,
        with nothing to re-tune when those change.
        """
        if self.bin.fault_mode == "HOT":
            headroom = settings.TEMP_FIRE_MAX - settings.TEMP_NORMAL_MAX
            self.bin.temperature = (
                settings.TEMP_NORMAL_MAX + headroom * self.bin.fill_pct / 100
            )
            return

        self.bin.temperature = min(
            settings.TEMP_NORMAL_MAX,
            max(
                settings.TEMP_NORMAL_MIN,
                self.bin.temperature
                + uniform(-0.5, 0.5),
            ),
        )
