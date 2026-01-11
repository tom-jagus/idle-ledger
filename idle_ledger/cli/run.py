import time
from datetime import date, datetime, time as dt_time, timedelta

from idle_ledger.engine.blocks import BlockManager
from idle_ledger.engine.state import classify_state
from idle_ledger.engine.types import State
from idle_ledger.providers.linux import LinuxProvider
from idle_ledger.store import (
    TransitionLogger,
    daily_journal_path,
    load_config,
    load_day,
    load_linux_options,
    transition_log_path,
    write_day_atomic,
)


def _validate_config(*, threshold_seconds: int, poll_seconds: float) -> None:
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be > 0")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")


def main():
    config, config_meta = load_config()
    linux_opts = load_linux_options()

    _validate_config(threshold_seconds=config.threshold_seconds, poll_seconds=config.poll_seconds)

    provider = LinuxProvider(
        threshold_seconds=config.threshold_seconds,
        prefer_hypridle=bool(linux_opts.get("prefer_hypridle", True)),
    )

    logger = TransitionLogger()

    current_day: date | None = None
    block_manager: BlockManager | None = None
    current_state: State | None = None
    last_heartbeat_mono: float | None = None

    print("Starting idle-ledger run mode (Ctrl+C to stop)")
    print(f"Config: {config_meta.get('path')}")

    try:
        while True:
            snapshot = provider.get_snapshot()

            if current_day is None:
                current_day = snapshot.now_wall.date()
                block_manager = load_day(day=current_day) or BlockManager()
                # Resume policy: never continue an "open" block across restarts.
                # We start a new block based on the first live snapshot.
                current_state = None
                last_heartbeat_mono = snapshot.now_mono

                print(f"Transition log: {transition_log_path(current_day)}")
                print(f"Daily journal: {daily_journal_path(current_day)}")

            snap_day = snapshot.now_wall.date()
            if snap_day != current_day:
                midnight = datetime.combine(snap_day, dt_time.min, tzinfo=snapshot.now_wall.tzinfo)

                if block_manager is not None and current_state is not None:
                    block_manager.close_current(midnight)
                    write_day_atomic(day=current_day, config=config, manager=block_manager)

                    logger.append(
                        when=midnight,
                        event={
                            "event": "rollover",
                            "from": current_day.isoformat(),
                            "to": snap_day.isoformat(),
                            "state": current_state.value,
                        },
                    )

                # Start a new day file with a carried-over state.
                current_day = snap_day
                block_manager = BlockManager()
                if current_state is not None:
                    block_manager.open_new(current_state, midnight)
                    write_day_atomic(day=current_day, config=config, manager=block_manager)
                    last_heartbeat_mono = snapshot.now_mono

                print(f"Transition log: {transition_log_path(current_day)}")
                print(f"Daily journal: {daily_journal_path(current_day)}")

            if block_manager is None or current_day is None:
                # Defensive: should not happen.
                time.sleep(config.poll_seconds)
                continue

            new_state = classify_state(snapshot, config)

            if current_state is None:
                block_manager.transition(new_state, snapshot.now_wall)
                current_state = new_state
                logger.log_transition(
                    when=snapshot.now_wall,
                    prev_state=None,
                    next_state=new_state,
                    snapshot=snapshot,
                )
                write_day_atomic(day=current_day, config=config, manager=block_manager)
                last_heartbeat_mono = snapshot.now_mono

            elif new_state != current_state:
                threshold_subtract = None
                if current_state == State.ACTIVITY and new_state == State.BREAK:
                    if snapshot.idle_seconds is not None:
                        last_active = snapshot.now_wall - timedelta(seconds=snapshot.idle_seconds)
                        threshold_subtract = last_active + timedelta(
                            seconds=config.threshold_seconds
                        )

                block_manager.transition(new_state, snapshot.now_wall, threshold_subtract)

                logger.log_transition(
                    when=snapshot.now_wall,
                    prev_state=current_state,
                    next_state=new_state,
                    snapshot=snapshot,
                )

                current_state = new_state
                write_day_atomic(day=current_day, config=config, manager=block_manager)
                last_heartbeat_mono = snapshot.now_mono

            # Journal heartbeat: checkpoint current open block end.
            if (
                last_heartbeat_mono is not None
                and snapshot.now_mono - last_heartbeat_mono >= config.journal_heartbeat_seconds
            ):
                write_day_atomic(day=current_day, config=config, manager=block_manager)
                last_heartbeat_mono = snapshot.now_mono

            time.sleep(config.poll_seconds)

    except KeyboardInterrupt:
        print("\nStopping...")
        if current_day is not None and block_manager is not None:
            write_day_atomic(day=current_day, config=config, manager=block_manager)
    finally:
        provider.close()


if __name__ == "__main__":
    main()
