from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date

from idle_ledger.store import (
    daily_journal_path,
    get_config_path,
    get_daily_journal_dir,
    get_transition_logs_dir,
    load_config,
    transition_log_path,
)


def _systemd_status() -> dict:
    if sys.platform != "linux":
        return {"available": False}

    systemctl = shutil.which("systemctl")
    if not systemctl:
        return {"available": False}

    enabled = subprocess.run(
        [systemctl, "--user", "is-enabled", "idle-ledger.service"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    active = subprocess.run(
        [systemctl, "--user", "is-active", "idle-ledger.service"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    return {
        "available": True,
        "enabled": enabled,
        "active": active,
    }


def _read_today_journal(today: date) -> dict | None:
    path = daily_journal_path(today)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    today = date.today()

    config, config_meta = load_config(create_if_missing=False)
    sysd = _systemd_status()
    journal = _read_today_journal(today)

    print("idle-ledger status")

    if sysd.get("available"):
        print(f"service enabled: {sysd.get('enabled')}")
        print(f"service active: {sysd.get('active')}")
    else:
        print("service enabled: unknown (no systemctl)")
        print("service active: unknown (no systemctl)")

    print(f"config: {get_config_path()}")
    if config_meta.get("error"):
        print(f"config error: {config_meta.get('error')}")

    print(f"data journal dir: {get_daily_journal_dir()}")
    print(f"data logs dir: {get_transition_logs_dir()}")
    print(f"today journal: {daily_journal_path(today)}")
    print(f"today transitions: {transition_log_path(today)}")

    if journal is None:
        print("today totals: unavailable (no journal yet)")
        print("current block: unavailable")
        return 0

    totals_raw = journal.get("totals")
    totals: dict = totals_raw if isinstance(totals_raw, dict) else {}
    activity_seconds = totals.get("activity_seconds")
    break_seconds = totals.get("break_seconds")

    print(f"today totals: activity={activity_seconds}s break={break_seconds}s")

    blocks = journal.get("blocks")
    if isinstance(blocks, list) and blocks:
        last = blocks[-1]
        if isinstance(last, dict):
            block_type = last.get("type")
            block_seconds = last.get("seconds")
            is_open = bool(last.get("open"))
            print(f"current block: type={block_type} seconds={block_seconds} open={is_open}")
        else:
            print("current block: unavailable")
    else:
        print("current block: unavailable")

    # Config summary
    print(
        "settings: "
        f"threshold={config.threshold_seconds}s "
        f"poll={config.poll_seconds}s "
        f"heartbeat={config.journal_heartbeat_seconds}s "
        f"target={config.daily_target_minutes}min "
        f"week_start={config.week_start} "
        f"inhibitor_as_activity={config.treat_inhibitor_as_activity}"
    )

    return 0
