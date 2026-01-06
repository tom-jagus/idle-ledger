from datetime import datetime, timezone
import time

import pytest

from idle_ledger.engine.types import Snapshot, Config, State
from idle_ledger.engine.state import classify_state


def test_classify_state_locked_forces_break():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=10,
        locked=True,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.BREAK


def test_classify_state_idle_none_fails_open():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=None,
        locked=False,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.ACTIVITY


def test_classify_state_idle_under_threshold():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=10,
        locked=False,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.ACTIVITY


def test_classify_state_idle_over_threshold():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=500,
        locked=False,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.BREAK


def test_classify_state_idle_at_threshold():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=300,
        locked=False,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.ACTIVITY


def test_classify_state_inhibitor_with_config_true():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=500,
        locked=False,
        inhibited=True,
    )
    config = Config(threshold_seconds=300, treat_inhibitor_as_activity=True)
    result = classify_state(snapshot, config)
    assert result == State.ACTIVITY


def test_classify_state_inhibitor_with_config_false():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=500,
        locked=False,
        inhibited=True,
    )
    config = Config(threshold_seconds=300, treat_inhibitor_as_activity=False)
    result = classify_state(snapshot, config)
    assert result == State.BREAK


def test_classify_state_priority_locked_over_idle():
    snapshot = Snapshot(
        now_wall=datetime.now(timezone.utc),
        now_mono=time.monotonic(),
        idle_seconds=0,
        locked=True,
        inhibited=None,
    )
    config = Config(threshold_seconds=300)
    result = classify_state(snapshot, config)
    assert result == State.BREAK
