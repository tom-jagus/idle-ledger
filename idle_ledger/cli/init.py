from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _systemd_user_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "systemd" / "user"
    return Path.home() / ".config" / "systemd" / "user"


def _detect_exec_start() -> str:
    """Return an ExecStart string usable by systemd.

    Preference:
    1) Absolute path to `idle-ledger` script on PATH
    2) sys.executable -m idle_ledger.cli run
    """

    exe = shutil.which("idle-ledger")
    if exe:
        return f"{exe} run"

    # Fallback for editable installs / venv.
    return f"{sys.executable} -m idle_ledger.cli run"


def _render_service(*, exec_start: str) -> str:
    return (
        "[Unit]\n"
        "Description=idle-ledger activity/break tracker\n"
        "After=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_start}\n"
        "Restart=on-failure\n"
        "RestartSec=3\n"
        "\n"
        "# Ensure sane XDG dirs (optional)\n"
        "Environment=XDG_CONFIG_HOME=%h/.config\n"
        "Environment=XDG_DATA_HOME=%h/.local/share\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def main(*, force: bool = False) -> int:
    if sys.platform != "linux":
        print("init is currently supported only on Linux (systemd user)")
        return 1

    systemctl = shutil.which("systemctl")
    if not systemctl:
        print("systemctl not found; cannot enable systemd user service")
        return 1

    unit_dir = _systemd_user_dir()
    unit_path = unit_dir / "idle-ledger.service"

    unit_dir.mkdir(parents=True, exist_ok=True)

    if unit_path.exists() and not force:
        print(f"Service already exists: {unit_path}")
        print("Re-run with --force to overwrite")
        return 1

    exec_start = _detect_exec_start()
    unit_path.write_text(_render_service(exec_start=exec_start), encoding="utf-8")

    try:
        subprocess.run([systemctl, "--user", "daemon-reload"], check=True)
        subprocess.run([systemctl, "--user", "enable", "--now", "idle-ledger.service"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"systemctl failed: {e}")
        print(f"Unit written to: {unit_path}")
        print("You can try manually:")
        print("  systemctl --user daemon-reload")
        print("  systemctl --user enable --now idle-ledger.service")
        return 1

    print(f"Installed and enabled: {unit_path}")
    print("Check status:")
    print("  systemctl --user status idle-ledger.service")
    return 0
