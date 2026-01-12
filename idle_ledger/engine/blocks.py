from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

from .types import State, Block


@dataclass
class Totals:
    activity_seconds: int = 0
    break_seconds: int = 0


class BlockManager:
    def __init__(self):
        self.blocks: List[Block] = []
        self._current_block: Block | None = None

    def get_current_block(self) -> Block | None:
        return self._current_block

    def get_current_state(self) -> State | None:
        if self._current_block is not None:
            return self._current_block.type
        if self.blocks:
            return self.blocks[-1].type
        return None

    def close_current(self, end: datetime) -> Block | None:
        if self._current_block is None:
            return None
        self._current_block.end = end
        closed = self._current_block
        self.blocks.append(closed)
        self._current_block = None
        return closed

    def open_new(self, state: State, start: datetime) -> None:
        self._current_block = Block(type=state, start=start, end=None)

    def load(self, *, blocks: list[Block], current_block: Block | None) -> None:
        self.blocks = blocks
        self._current_block = current_block

    def transition(
        self, new_state: State, now: datetime, threshold_subtract: datetime | None = None
    ):
        """Handle state transition.

        Args:
            new_state: New state (ACTIVITY or BREAK)
            now: Current timestamp
            threshold_subtract: For ACTIVITY->BREAK, time when break should start (retroactive cut)
        """
        if self._current_block is None:
            self._current_block = Block(type=new_state, start=now, end=None)
            return

        if self._current_block.type == new_state:
            return

        if (
            threshold_subtract
            and self._current_block.type == State.ACTIVITY
            and new_state == State.BREAK
        ):
            # Guard against time anomalies (e.g. threshold_subtract earlier than the
            # block start after a midnight rollover).
            end_time = threshold_subtract
            if end_time < self._current_block.start:
                end_time = self._current_block.start
            if end_time > now:
                end_time = now
            self._current_block.end = end_time
            next_start = end_time
        else:
            self._current_block.end = now
            next_start = now

        self.blocks.append(self._current_block)
        self._current_block = Block(type=new_state, start=next_start, end=None)

    def get_totals(self) -> Totals:
        """Calculate totals from blocks."""
        activity = 0
        break_time = 0

        for block in self.blocks:
            end = block.end or datetime.now(block.start.tzinfo)
            duration = max(0, int((end - block.start).total_seconds()))

            if block.type == State.ACTIVITY:
                activity += duration
            else:
                break_time += duration

        if self._current_block:
            end = self._current_block.end or datetime.now(self._current_block.start.tzinfo)
            duration = max(0, int((end - self._current_block.start).total_seconds()))

            if self._current_block.type == State.ACTIVITY:
                activity += duration
            else:
                break_time += duration

        return Totals(activity_seconds=activity, break_seconds=break_time)
