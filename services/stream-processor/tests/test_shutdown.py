"""Tests for stopping the streaming application cleanly.

Before this, SIGTERM was ignored: the main thread sat inside an unbounded
`awaitAnyTermination`, Python could not run the handler until that call
returned, and Docker sent SIGKILL after the grace period. Every stop reported
as exit 137. Nothing was lost - checkpoints and idempotent writes cover a kill -
but a crash exit code on an ordinary stop is the wrong signal to leave behind.
"""

import threading

import pytest

from main import run


class FakeQuery:
    def __init__(self, name):
        self.name = name
        self.isActive = True
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.isActive = False


class FakeStreams:
    def __init__(self, terminates_after=None, raises=None):
        self.calls = 0
        self._terminates_after = terminates_after
        self._raises = raises

    def awaitAnyTermination(self, timeout=None):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._terminates_after is not None and self.calls >= self._terminates_after


class FakeSession:
    def __init__(self, streams):
        self.streams = streams
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_a_stop_request_stops_every_query_and_the_session():
    queries = [FakeQuery("bin_events"), FakeQuery("bin_state")]
    session = FakeSession(FakeStreams())
    stop_requested = threading.Event()
    stop_requested.set()

    run(session, queries, stop_requested)

    assert all(query.stopped for query in queries)
    assert session.stopped


def test_the_wait_is_bounded_so_a_signal_is_noticed():
    """An unbounded wait is what swallowed SIGTERM."""
    queries = [FakeQuery("bin_state")]
    streams = FakeStreams()
    session = FakeSession(streams)
    stop_requested = threading.Event()

    # Set the flag from the fake's third poll, as a signal handler would.
    original = streams.awaitAnyTermination

    def poll(timeout=None):
        if streams.calls >= 2:
            stop_requested.set()
        return original(timeout=timeout)

    streams.awaitAnyTermination = poll

    run(session, queries, stop_requested)

    assert streams.calls == 3
    assert session.stopped


def test_a_query_ending_on_its_own_also_shuts_down():
    queries = [FakeQuery("bin_state")]
    session = FakeSession(FakeStreams(terminates_after=1))

    run(session, queries, threading.Event())

    assert queries[0].stopped
    assert session.stopped


def test_a_failing_query_still_surfaces_its_error():
    """The failure must not be swallowed by the shutdown path."""
    session = FakeSession(FakeStreams(raises=RuntimeError("query failed")))

    with pytest.raises(RuntimeError, match="query failed"):
        run(session, [FakeQuery("bin_state")], threading.Event())


def test_an_already_stopped_query_is_not_stopped_twice():
    query = FakeQuery("bin_state")
    query.isActive = False
    session = FakeSession(FakeStreams())
    stop_requested = threading.Event()
    stop_requested.set()

    run(session, [query], stop_requested)

    assert not query.stopped
    assert session.stopped
