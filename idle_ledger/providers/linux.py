import os
import subprocess
import time
from datetime import datetime, timezone

from ..engine.types import Snapshot


class LinuxProvider:
    def __init__(self):
        self._session_id = None
        self._user = None

    def _get_user(self) -> str:
        if self._user is None:
            self._user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
        return self._user

    def _find_session_id(self) -> str | None:
        """Find active session for current user.

        Priority:
        1. Session with State=active
        2. First session found for user

        Returns:
            Session ID string or None if not found
        """
        user = self._get_user()
        try:
            result = subprocess.run(
                ["loginctl", "list-sessions"],
                capture_output=True,
                text=True,
                check=True,
            )
            lines = result.stdout.strip().split("\n")
            user_session_ids = []

            for line in lines[1:]:
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
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _get_session_properties(self, session_id: str) -> dict:
        """Get session properties from loginctl.

        Returns:
            Dictionary of property name -> value
        """
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
            props = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    props[key] = value
            return props
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}

    def get_snapshot(self) -> Snapshot:
        """Get current system snapshot.

        Returns:
            Snapshot with current idle, locked, inhibited status
        """
        now_wall = datetime.now(timezone.utc)
        now_mono = time.monotonic()

        if self._session_id is None:
            self._session_id = self._find_session_id()

        if self._session_id is None:
            return Snapshot(
                now_wall=now_wall,
                now_mono=now_mono,
                idle_seconds=None,
                locked=None,
                inhibited=None,
                provider_meta={"error": "no_session_found"},
            )

        props = self._get_session_properties(self._session_id)

        idle_seconds = None
        idle_since = props.get("IdleSinceHintMonotonic", "0")
        idle_hint = props.get("IdleHint", "no")

        if idle_hint == "yes" and idle_since and idle_since != "0":
            try:
                idle_since_mono = float(idle_since)
                idle_seconds = int(now_mono - idle_since_mono)
            except ValueError:
                pass
        elif idle_hint == "no":
            idle_seconds = 0

        locked = None
        locked_hint = props.get("LockedHint", "no")
        if locked_hint in ("yes", "no"):
            locked = locked_hint == "yes"

        return Snapshot(
            now_wall=now_wall,
            now_mono=now_mono,
            idle_seconds=idle_seconds,
            locked=locked,
            inhibited=None,
            provider_meta={
                "session_id": self._session_id,
                "raw_props": props,
            },
        )
