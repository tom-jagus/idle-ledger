import sys
import time
from datetime import timedelta

from idle_ledger.engine.blocks import BlockManager
from idle_ledger.engine.state import classify_state
from idle_ledger.engine.types import State
from idle_ledger.providers.linux import LinuxProvider
from idle_ledger.store import load_config, load_linux_options


def main():
    """Run debug CLI - prints live snapshot + state + totals."""

    config, config_meta = load_config()
    linux_opts = load_linux_options()

    provider = LinuxProvider(
        threshold_seconds=config.threshold_seconds,
        prefer_hypridle=bool(linux_opts.get("prefer_hypridle", True)),
    )
    block_manager = BlockManager()

    current_state: State | None = None

    print("Starting idle-ledger debug mode")
    print(f"Config: {config_meta.get('path')}")
    if config_meta.get("created"):
        print("Config created with defaults")
    elif config_meta.get("loaded"):
        print("Config loaded")
    if config_meta.get("error"):
        print(f"Config error: {config_meta.get('error')}")
    print(f"Threshold: {config.threshold_seconds}s, Poll: {config.poll_seconds}s")
    print("-" * 50)

    provider_mode_logged = False

    use_tty_ui = sys.stdout.isatty()

    def _render(lines: list[str]) -> None:
        if use_tty_ui:
            # Clear screen + move cursor home.
            sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write("\n".join(lines))
        sys.stdout.write("\n")
        sys.stdout.flush()

    try:
        while True:
            snapshot = provider.get_snapshot()
            new_state = classify_state(snapshot, config)

            meta = snapshot.provider_meta or {}

            lines: list[str] = []
            lines.append("idle-ledger debug")
            lines.append(f"timestamp: {snapshot.now_wall.isoformat()}")
            lines.append(f"threshold: {config.threshold_seconds}s poll: {config.poll_seconds}s")
            lines.append(
                "provider_mode: "
                f"method={meta.get('method')} "
                f"hypridle_pid={meta.get('hypridle_pid')} "
                f"locked_method={meta.get('locked_method')} "
                f"logind_idle_supported={meta.get('logind_idle_supported')} "
                f"idle_forced_break={meta.get('idle_forced_break')} "
                f"idle_reason={meta.get('idle_reason')}"
            )
            lines.append("-" * 50)

            if current_state is None:
                block_manager.transition(new_state, snapshot.now_wall)
                current_state = new_state
            elif new_state != current_state:
                threshold_subtract = None
                if current_state == State.ACTIVITY and new_state == State.BREAK:
                    if snapshot.idle_seconds is not None:
                        last_active = snapshot.now_wall - timedelta(seconds=snapshot.idle_seconds)
                        threshold_subtract = last_active + timedelta(
                            seconds=config.threshold_seconds
                        )

                block_manager.transition(new_state, snapshot.now_wall, threshold_subtract)
                current_state = new_state

            totals = block_manager.get_totals()

            lines.append(f"idle_seconds: {snapshot.idle_seconds}")
            lines.append(f"locked: {snapshot.locked}")
            lines.append(f"inhibited: {snapshot.inhibited}")
            lines.append(f"state: {new_state.value}")
            lines.append(f"totals: activity={totals.activity_seconds}s break={totals.break_seconds}s")
            lines.append("-" * 50)

            if use_tty_ui:
                lines.append("Ctrl+C to exit")

            _render(lines)

            time.sleep(config.poll_seconds)

    except KeyboardInterrupt:
        print("\nExiting debug mode...")
        totals = block_manager.get_totals()
        print(f"Final totals: activity={totals.activity_seconds}s, break={totals.break_seconds}s")


if __name__ == "__main__":
    main()
