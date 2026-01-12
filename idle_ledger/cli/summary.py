from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from idle_ledger.engine.types import Config
from idle_ledger.store import daily_journal_path, load_config


@dataclass
class _Totals:
    activity_seconds: int
    break_seconds: int


def _round_to_minute(seconds: int) -> int:
    # Round to nearest minute, half-up.
    return int(((seconds + 30) // 60) * 60)


def _format_hm(seconds: int) -> str:
    s = _round_to_minute(max(0, int(seconds)))
    minutes = s // 60
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}m"


def _load_totals_for_day(day: date) -> _Totals | None:
    path = daily_journal_path(day)
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    blocks = raw.get("blocks")
    if not isinstance(blocks, list):
        return None

    activity = 0
    break_time = 0

    for item in blocks:
        if not isinstance(item, dict):
            continue

        t = item.get("type")
        start_s = item.get("start")
        end_s = item.get("end")
        if not isinstance(t, str) or not isinstance(start_s, str) or not isinstance(end_s, str):
            continue

        try:
            start = datetime.fromisoformat(start_s)
            end = datetime.fromisoformat(end_s)
        except ValueError:
            continue

        dur = max(0, int((end - start).total_seconds()))
        if t == "activity":
            activity += dur
        elif t == "break":
            break_time += dur

    return _Totals(activity_seconds=activity, break_seconds=break_time)


def _week_start(today: date, *, week_start: str) -> date:
    ws = week_start.strip().lower()
    if ws == "sunday":
        # Convert weekday (Mon=0..Sun=6) into days since Sunday.
        days_since_sun = (today.weekday() + 1) % 7
        return today - timedelta(days=days_since_sun)

    # ISO week (Mon start)
    return today - timedelta(days=today.weekday())


def _print_period(*, label: str, totals: _Totals, config: Config, target_days: int) -> None:
    target_seconds = config.daily_target_minutes * 60 * target_days
    delta = totals.activity_seconds - target_seconds

    if delta >= 0:
        delta_label = "excess"
        delta_seconds = delta
    else:
        delta_label = "remaining"
        delta_seconds = -delta

    print(
        f"{label}: "
        f"activity {_format_hm(totals.activity_seconds)}, "
        f"break {_format_hm(totals.break_seconds)}, "
        f"{delta_label} {_format_hm(delta_seconds)} "
        f"(target {_format_hm(target_seconds)})"
    )


def main(period: str = "today") -> int:
    config, _ = load_config()

    today = date.today()
    period_norm = (period or "today").strip().lower()

    if period_norm in {"today", ""}:
        totals = _load_totals_for_day(today)
        if totals is None:
            print("today: no journal yet")
            return 0
        _print_period(label="today", totals=totals, config=config, target_days=1)
        return 0

    if period_norm == "yesterday":
        day = today - timedelta(days=1)
        totals = _load_totals_for_day(day)
        if totals is None:
            print("yesterday: no journal")
            return 0
        _print_period(label="yesterday", totals=totals, config=config, target_days=1)
        return 0

    if period_norm == "week":
        start = _week_start(today, week_start=config.week_start)
        days = (today - start).days + 1

        activity = 0
        break_time = 0
        for i in range(days):
            d = start + timedelta(days=i)
            t = _load_totals_for_day(d)
            if t is None:
                continue
            activity += t.activity_seconds
            break_time += t.break_seconds

        totals = _Totals(activity_seconds=activity, break_seconds=break_time)
        _print_period(label="week", totals=totals, config=config, target_days=days)
        return 0

    raise SystemExit(f"Unknown period: {period}")
