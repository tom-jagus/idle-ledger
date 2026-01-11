from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Final


class State(Enum):
    ACTIVITY = "activity"
    BREAK = "break"


DEFAULT_THRESHOLD_SECONDS: Final[int] = 300
DEFAULT_POLL_SECONDS: Final[float] = 2.0
DEFAULT_JOURNAL_HEARTBEAT_SECONDS: Final[int] = 30


@dataclass
class Config:
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS
    treat_inhibitor_as_activity: bool = True
    poll_seconds: float = DEFAULT_POLL_SECONDS
    journal_heartbeat_seconds: int = DEFAULT_JOURNAL_HEARTBEAT_SECONDS


@dataclass
class Block:
    type: State
    start: datetime
    end: datetime | None = None


@dataclass
class Snapshot:
    now_wall: datetime
    now_mono: float
    idle_seconds: int | None
    locked: bool | None
    inhibited: bool | None = None
    provider_meta: dict | None = None

    def __post_init__(self):
        if self.provider_meta is None:
            self.provider_meta = {}
