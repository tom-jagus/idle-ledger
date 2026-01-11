from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

try:
    from platformdirs import user_data_dir

    def _user_data_dir(app_name: str) -> str:
        return user_data_dir(app_name)

except ImportError:  # pragma: no cover

    def _user_data_dir(app_name: str) -> str:
        if sys.platform.startswith("win"):
            base = os.environ.get("LOCALAPPDATA")
            if base:
                return str(Path(base) / app_name)
            return str(Path.home() / "AppData" / "Local" / app_name)

        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return str(Path(base) / app_name)
        return str(Path.home() / ".local" / "share" / app_name)


def get_data_dir() -> Path:
    return Path(_user_data_dir("idle-ledger"))


def get_transition_logs_dir() -> Path:
    return get_data_dir() / "transition-logs"


def get_daily_journal_dir() -> Path:
    return get_data_dir() / "daily-journal"


def transition_log_path(day: date) -> Path:
    return get_transition_logs_dir() / f"{day.isoformat()}.jsonl"


def daily_journal_path(day: date) -> Path:
    return get_daily_journal_dir() / f"{day.isoformat()}.json"
