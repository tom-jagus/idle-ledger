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
            self._current_block.end = threshold_subtract
        else:
            self._current_block.end = now

        self.blocks.append(self._current_block)
        start_time = threshold_subtract if threshold_subtract else now
        self._current_block = Block(type=new_state, start=start_time, end=None)

    def get_totals(self) -> Totals:
        """Calculate totals from blocks."""
        activity = 0
        break_time = 0

        for block in self.blocks:
            end = block.end or datetime.now(block.start.tzinfo)
            duration = int((end - block.start).total_seconds())

            if block.type == State.ACTIVITY:
                activity += duration
            else:
                break_time += duration

        return Totals(activity_seconds=activity, break_seconds=break_time)
