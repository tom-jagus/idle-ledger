import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..engine.types import Snapshot


@dataclass
class _HypridleState:
    fifo_path: Path
    fifo_fd_read: int
    fifo_fd_keepalive_write: int
    config_path: Path
    process: subprocess.Popen[str]
    is_idle: bool = False
    idle_start_mono: float | None = None
    last_error: str | None = None


class LinuxProvider:
    """Linux provider.

    Priority order:
    1) Hypridle events (Hyprland sessions only)
    2) systemd-logind via loginctl

    Notes:
    - Hypridle provides robust Wayland idle detection on Hyprland and respects inhibitors.
    - loginctl provides lock state everywhere systemd-logind is present; idle hints may be
      unreliable on some compositors.
    """

    def __init__(self, *, threshold_seconds: int, prefer_hypridle: bool = True):
        self._threshold_seconds = int(threshold_seconds)
        self._prefer_hypridle = prefer_hypridle

        self._session_id: str | None = None
        self._user: str | None = None

        self._hypridle: _HypridleState | None = None
        self._hypridle_attempted = False
        self._hypridle_restart_after_mono: float | None = None

    def _get_user(self) -> str:
        if self._user is None:
            self._user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
        return self._user

    def _find_session_id(self) -> str | None:
        """Find active session for current user."""

        user = self._get_user()
        try:
            result = subprocess.run(
                ["loginctl", "list-sessions", "--no-legend", "--no-pager"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        user_session_ids: list[str] = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] == user:
                user_session_ids.append(parts[0])

        if not user_session_ids:
            return None

        for session_id in user_session_ids:
            props = self._get_session_properties(session_id)
            if props.get("State") == "active":
                return session_id

        return user_session_ids[0]

    def _get_session_properties(self, session_id: str) -> dict[str, str]:
        """Get session properties from loginctl."""

        try:
            result = subprocess.run(
                [
                    "loginctl",
                    "show-session",
                    session_id,
                    "--property=IdleSinceHintMonotonic",
                    "--property=LockedHint",
                    "--property=IdleHint",
                    "--property=State",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}

        props: dict[str, str] = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                props[key] = value
        return props

    def _get_locked(self, session_id: str) -> bool | None:
        props = self._get_session_properties(session_id)
        locked_hint = props.get("LockedHint")
        if locked_hint in ("yes", "no"):
            return locked_hint == "yes"
        return None

    def _get_hyprland_locked(self) -> bool | None:
        """Best-effort Hyprland lock detection.

        On Hyprland, `loginctl LockedHint` is often not updated by `hyprlock`.

        Strategy:
        1) If a `hyprlock` process exists -> locked.
        2) If `hyprctl -j layers` exposes a lock namespace -> locked.

        Returns None if we can't determine anything.
        """

        # Process-based: works even if hyprlock uses session-lock protocol (not layer-shell).
        if shutil.which("pgrep") is not None:
            try:
                p = subprocess.run(["pgrep", "-x", "hyprlock"], capture_output=True, text=True)
                if p.returncode == 0:
                    return True
            except OSError:
                pass

        # Layer-based: some setups expose lock surfaces as layers.
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return None
        if shutil.which("hyprctl") is None:
            return None

        try:
            result = subprocess.run(
                ["hyprctl", "-j", "layers"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            raw = json.loads(result.stdout)
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            return None

        # raw is: {monitor: {levels: {"0": [..], "1": [..], ...}}}
        for monitor in raw.values():
            levels = monitor.get("levels") if isinstance(monitor, dict) else None
            if not isinstance(levels, dict):
                continue
            for layers in levels.values():
                if not isinstance(layers, list):
                    continue
                for layer in layers:
                    if not isinstance(layer, dict):
                        continue
                    namespace = layer.get("namespace")
                    if isinstance(namespace, str) and "hyprlock" in namespace.lower():
                        return True

        return False

    def _get_idle_seconds_logind(self, session_id: str, now_mono: float) -> int | None:
        props = self._get_session_properties(session_id)

        idle_hint = props.get("IdleHint")
        if idle_hint == "no":
            return 0
        if idle_hint != "yes":
            return None

        idle_since_raw = props.get("IdleSinceHintMonotonic")
        if not idle_since_raw:
            return None

        try:
            # systemd returns microseconds from CLOCK_MONOTONIC
            idle_since_us = int(idle_since_raw)
        except ValueError:
            return None

        now_us = int(now_mono * 1_000_000)
        if idle_since_us <= 0 or idle_since_us > now_us:
            return None

        return int((now_us - idle_since_us) / 1_000_000)

    def _get_inhibited(self) -> bool | None:
        """Detect whether idle inhibitors are active.

        Best-effort parsing of `loginctl list-inhibitors`. Returns:
        - True/False if determinable
        - None if unavailable
        """

        try:
            result = subprocess.run(
                ["loginctl", "list-inhibitors", "--no-legend", "--no-pager"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        inhibited = False
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            # Columns are: WHO UID USER PID COMM WHAT WHY MODE
            # `WHY` may contain spaces; `WHAT` is a single token at index 5.
            parts = line.split()
            if len(parts) < 6:
                continue

            what = parts[5]
            what_items = set(what.split(":"))
            if "idle" in what_items:
                inhibited = True
                break

        return inhibited

    def _should_try_hypridle(self) -> bool:
        if not self._prefer_hypridle:
            return False
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return False
        return shutil.which("hypridle") is not None

    def _ensure_hypridle(self, now_mono: float) -> None:
        if self._hypridle is not None:
            return
        if (
            self._hypridle_restart_after_mono is not None
            and now_mono < self._hypridle_restart_after_mono
        ):
            return
        if self._hypridle_attempted:
            return

        if not self._should_try_hypridle():
            # Conditions not met; allow later retries.
            self._hypridle_attempted = False
            return

        self._hypridle_attempted = True

        if (
            self._hypridle_restart_after_mono is not None
            and now_mono < self._hypridle_restart_after_mono
        ):
            return
        if self._hypridle_attempted:
            return
        self._hypridle_attempted = True

        if not self._should_try_hypridle():
            return

        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        work_dir = Path(runtime_dir) / "idle-ledger"
        work_dir.mkdir(parents=True, exist_ok=True)

        fifo_path = work_dir / f"hypridle-events.{os.getpid()}.fifo"
        config_path = work_dir / f"hypridle.{os.getpid()}.conf"

        try:
            if fifo_path.exists():
                fifo_path.unlink()
            os.mkfifo(fifo_path, 0o600)

            fifo_fd_read = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
            fifo_fd_keepalive_write = os.open(fifo_path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            # Fall back to logind; do not hard-fail the provider.
            self._hypridle = None
            self._hypridle_attempted = False
            self._hypridle_restart_after_mono = now_mono + 10.0
            return

        config_text = (
            "general {\n"
            "    ignore_dbus_inhibit = false\n"
            "    ignore_systemd_inhibit = false\n"
            "}\n\n"
            "listener {\n"
            f"    timeout = {self._threshold_seconds}\n"
            f"    on-timeout = sh -lc 'printf "
            '"timeout\\n" > '
            f'"{fifo_path}"\'\n'
            f"    on-resume = sh -lc 'printf "
            '"resume\\n" > '
            f'"{fifo_path}"\'\n'
            "}\n"
        )

        try:
            config_path.write_text(config_text, encoding="utf-8")
        except OSError:
            os.close(fifo_fd_read)
            os.close(fifo_fd_keepalive_write)
            try:
                fifo_path.unlink()
            except OSError:
                pass
            self._hypridle_attempted = False
            self._hypridle_restart_after_mono = now_mono + 10.0
            return

        try:
            process = subprocess.Popen(
                ["hypridle", "-c", str(config_path), "-q"],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            os.close(fifo_fd_read)
            os.close(fifo_fd_keepalive_write)
            try:
                fifo_path.unlink()
            except OSError:
                pass
            self._hypridle_attempted = False
            self._hypridle_restart_after_mono = now_mono + 10.0
            return

        self._hypridle = _HypridleState(
            fifo_path=fifo_path,
            fifo_fd_read=fifo_fd_read,
            fifo_fd_keepalive_write=fifo_fd_keepalive_write,
            config_path=config_path,
            process=process,
        )

    def _drain_hypridle_events(self, now_mono: float) -> None:
        if self._hypridle is None:
            return

        if self._hypridle.process.poll() is not None:
            # Hypridle died (e.g. killed externally). Stop using it and allow a
            # later re-attempt with backoff.
            self._hypridle.last_error = "hypridle_exited"
            self._hypridle = None
            self._hypridle_attempted = False
            self._hypridle_restart_after_mono = now_mono + 5.0
            return

        try:
            data = os.read(self._hypridle.fifo_fd_read, 4096)
        except BlockingIOError:
            return
        except OSError:
            self._hypridle = None
            self._hypridle_attempted = False
            self._hypridle_restart_after_mono = now_mono + 10.0
            return

        if not data:
            return

        for raw_line in data.decode("utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if line == "timeout":
                self._hypridle.is_idle = True
                # hypridle fires exactly at timeout; approximate idle start at (now - threshold)
                self._hypridle.idle_start_mono = max(0.0, now_mono - self._threshold_seconds)
            elif line == "resume":
                self._hypridle.is_idle = False
                self._hypridle.idle_start_mono = None

    def get_snapshot(self) -> Snapshot:
        now_wall = datetime.now().astimezone()
        now_mono = time.monotonic()

        if self._session_id is None:
            self._session_id = self._find_session_id()

        provider_meta: dict = {}

        if self._session_id is None:
            return Snapshot(
                now_wall=now_wall,
                now_mono=now_mono,
                idle_seconds=None,
                locked=None,
                inhibited=None,
                provider_meta={"error": "no_session_found"},
            )

        locked_method = "loginctl"
        locked = self._get_locked(self._session_id)

        hypr_locked = self._get_hyprland_locked()
        if hypr_locked is not None:
            locked = hypr_locked
            locked_method = "hyprland"

        inhibited = self._get_inhibited()

        self._ensure_hypridle(now_mono)
        if self._hypridle is not None:
            self._drain_hypridle_events(now_mono)

            state = self._hypridle
            if state is not None:
                if state.is_idle and state.idle_start_mono is not None:
                    idle_seconds = int(max(0.0, now_mono - state.idle_start_mono))
                else:
                    idle_seconds = 0

                provider_meta.update(
                    {
                        "method": "hypridle",
                        "session_id": self._session_id,
                        "hypridle_pid": state.process.pid,
                        "locked_method": locked_method,
                    }
                )

                return Snapshot(
                    now_wall=now_wall,
                    now_mono=now_mono,
                    idle_seconds=idle_seconds,
                    locked=locked,
                    inhibited=inhibited,
                    provider_meta=provider_meta,
                )

        idle_seconds = self._get_idle_seconds_logind(self._session_id, now_mono)
        provider_meta.update(
            {"method": "loginctl", "session_id": self._session_id, "locked_method": locked_method}
        )

        return Snapshot(
            now_wall=now_wall,
            now_mono=now_mono,
            idle_seconds=idle_seconds,
            locked=locked,
            inhibited=inhibited,
            provider_meta=provider_meta,
        )

    def close(self) -> None:
        """Best-effort cleanup (hypridle process + FIFOs)."""

        state = self._hypridle
        self._hypridle = None
        self._hypridle_attempted = False
        self._hypridle_restart_after_mono = None
        if state is None:
            return

        try:
            state.process.terminate()
            state.process.wait(timeout=2)
        except Exception:
            try:
                state.process.kill()
            except Exception:
                pass

        for fd in (state.fifo_fd_read, state.fifo_fd_keepalive_write):
            try:
                os.close(fd)
            except OSError:
                pass

        for path in (state.fifo_path, state.config_path):
            try:
                path.unlink()
            except OSError:
                pass
