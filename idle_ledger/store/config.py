from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

try:
    from platformdirs import user_config_dir

    def _user_config_dir(app_name: str) -> str:
        return user_config_dir(app_name)

except ImportError:  # pragma: no cover

    def _user_config_dir(app_name: str) -> str:
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA")
            if base:
                return str(Path(base) / app_name)
            return str(Path.home() / "AppData" / "Roaming" / app_name)

        base = os.environ.get("XDG_CONFIG_HOME")
        if base:
            return str(Path(base) / app_name)
        return str(Path.home() / ".config" / app_name)


from idle_ledger.engine.types import Config


def get_config_path() -> Path:
    return Path(_user_config_dir("idle-ledger")) / "config.toml"


def default_config_toml(config: Config | None = None) -> str:
    cfg = config or Config()
    # Keep it minimal and editable.
    return (
        "# idle-ledger configuration\n"
        "# Location: ~/.config/idle-ledger/config.toml (or XDG_CONFIG_HOME)\n"
        "\n"
        f"threshold_seconds = {cfg.threshold_seconds}\n"
        f"poll_seconds = {cfg.poll_seconds}\n"
        f"journal_heartbeat_seconds = {cfg.journal_heartbeat_seconds}\n"
        f"treat_inhibitor_as_activity = {str(cfg.treat_inhibitor_as_activity).lower()}\n"
        "\n"
        "[summary]\n"
        "# Daily activity target (minutes)\n"
        f"daily_target_minutes = {cfg.daily_target_minutes}\n"
        '# Week start: "iso" (Mon) or "sunday"\n'
        f'week_start = "{cfg.week_start}"\n'
        "\n"
        "[linux]\n"
        "# Prefer hypridle (Hyprland) when installed\n"
        "prefer_hypridle = true\n"
    )


def ensure_default_config_file(path: Path | None = None) -> Path:
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(default_config_toml(), encoding="utf-8")
    return config_path


def load_config(path: Path | None = None, *, create_if_missing: bool = True) -> tuple[Config, dict]:
    """Load config.toml, returning (Config, meta).

    Meta contains useful diagnostics for debug output.
    """

    config_path = path or get_config_path()
    meta: dict = {"path": str(config_path), "loaded": False, "created": False}

    if create_if_missing:
        before = config_path.exists()
        ensure_default_config_file(config_path)
        meta["created"] = not before

    if not config_path.exists():
        return Config(), meta

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        meta["error"] = f"config_read_error: {e}"
        return Config(), meta

    cfg = Config()

    if isinstance(raw.get("threshold_seconds"), int):
        cfg.threshold_seconds = int(raw["threshold_seconds"])
    if isinstance(raw.get("poll_seconds"), int | float):
        cfg.poll_seconds = float(raw["poll_seconds"])

    heartbeat = raw.get("journal_heartbeat_seconds")
    if isinstance(heartbeat, int):
        # Guardrail: heartbeat too low causes excessive fsync/write churn.
        cfg.journal_heartbeat_seconds = max(int(heartbeat), 30)

    if isinstance(raw.get("treat_inhibitor_as_activity"), bool):
        cfg.treat_inhibitor_as_activity = bool(raw["treat_inhibitor_as_activity"])

    summary = raw.get("summary")
    if isinstance(summary, dict):
        target = summary.get("daily_target_minutes")
        if isinstance(target, int) and target > 0:
            cfg.daily_target_minutes = target

        week_start = summary.get("week_start")
        if isinstance(week_start, str):
            week_start_norm = week_start.strip().lower()
            if week_start_norm in {"iso", "sunday"}:
                cfg.week_start = week_start_norm

    meta["loaded"] = True
    return cfg, meta


def load_linux_options(path: Path | None = None) -> dict:
    """Load Linux-specific options from config.toml."""

    config_path = path or get_config_path()
    if not config_path.exists():
        return {}

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}

    linux = raw.get("linux")
    return linux if isinstance(linux, dict) else {}
