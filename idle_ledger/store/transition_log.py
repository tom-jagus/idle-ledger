from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from idle_ledger.engine.types import Snapshot, State
from idle_ledger.store.paths import transition_log_path


@dataclass
class TransitionLogger:
    base_dir: Path | None = None

    def _ensure_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, when: datetime, event: dict) -> None:
        """Append a single JSON object as one line."""

        path = transition_log_path(when.date())
        self._ensure_dir(path)

        payload = {"ts": when.isoformat(), **event}
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

    def log_transition(
        self,
        *,
        when: datetime,
        prev_state: State | None,
        next_state: State,
        snapshot: Snapshot,
    ) -> None:
        meta = snapshot.provider_meta or {}

        event = {
            "event": "transition" if prev_state is not None else "start",
            "prev_state": prev_state.value if prev_state is not None else None,
            "next_state": next_state.value,
            "idle_seconds": snapshot.idle_seconds,
            "locked": snapshot.locked,
            "inhibited": snapshot.inhibited,
            "provider": {
                "method": meta.get("method"),
                "session_id": meta.get("session_id"),
            },
        }
        self.append(when=when, event=event)
