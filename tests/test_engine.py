from datetime import datetime, timedelta, timezone
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


def test_block_manager_first_block_creates_open_block():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.ACTIVITY, now)

    assert manager._current_block is not None
    assert manager._current_block.type == State.ACTIVITY
    assert manager._current_block.start == now
    assert manager._current_block.end is None
    assert len(manager.blocks) == 0


def test_block_manager_no_change_when_same_state():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.ACTIVITY, now)

    initial_block_id = id(manager._current_block)
    manager.transition(State.ACTIVITY, now + timedelta(seconds=10))

    assert id(manager._current_block) == initial_block_id
    assert len(manager.blocks) == 0


def test_block_manager_activity_to_break_normal():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.ACTIVITY, now)

    break_time = now + timedelta(seconds=100)
    manager.transition(State.BREAK, break_time)

    assert len(manager.blocks) == 1
    assert manager.blocks[0].type == State.ACTIVITY
    assert manager.blocks[0].start == now
    assert manager.blocks[0].end == break_time
    assert manager._current_block.type == State.BREAK
    assert manager._current_block.start == break_time


def test_block_manager_break_to_activity_normal():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.BREAK, now)

    activity_time = now + timedelta(seconds=100)
    manager.transition(State.ACTIVITY, activity_time)

    assert len(manager.blocks) == 1
    assert manager.blocks[0].type == State.BREAK
    assert manager._current_block.type == State.ACTIVITY
    assert manager._current_block.start == activity_time


def test_block_manager_threshold_subtraction():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.ACTIVITY, now)

    break_time = now + timedelta(seconds=500)
    threshold_subtract = now + timedelta(seconds=300)
    manager.transition(State.BREAK, break_time, threshold_subtract=threshold_subtract)

    assert len(manager.blocks) == 1
    assert manager.blocks[0].end == threshold_subtract
    assert manager._current_block.start == threshold_subtract

    activity_duration = (manager.blocks[0].end - manager.blocks[0].start).total_seconds()
    assert activity_duration == 300


def test_block_manager_multiple_transitions():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)

    manager.transition(State.ACTIVITY, now)
    manager.transition(State.BREAK, now + timedelta(seconds=100))
    manager.transition(State.ACTIVITY, now + timedelta(seconds=200))
    manager.transition(State.BREAK, now + timedelta(seconds=300))

    assert len(manager.blocks) == 3
    assert manager.blocks[0].type == State.ACTIVITY
    assert manager.blocks[1].type == State.BREAK
    assert manager.blocks[2].type == State.ACTIVITY
    assert manager._current_block.type == State.BREAK


def test_block_manager_totals_empty():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    totals = manager.get_totals()

    assert totals.activity_seconds == 0
    assert totals.break_seconds == 0


def test_block_manager_totals_single_block():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)
    manager.transition(State.ACTIVITY, now)
    manager.transition(State.BREAK, now + timedelta(seconds=100))

    totals = manager.get_totals()
    assert totals.activity_seconds == 100
    assert totals.break_seconds == 0


def test_block_manager_totals_mixed_blocks():
    from idle_ledger.engine.blocks import BlockManager

    manager = BlockManager()
    now = datetime.now(timezone.utc)

    manager.transition(State.ACTIVITY, now)
    manager.transition(State.BREAK, now + timedelta(seconds=100))
    manager.transition(State.ACTIVITY, now + timedelta(seconds=200))

    totals = manager.get_totals()
    assert totals.activity_seconds == 100
    assert totals.break_seconds == 100
