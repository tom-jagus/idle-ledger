from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from idle_ledger.engine.blocks import BlockManager
from idle_ledger.engine.types import Block, Config, State
from idle_ledger.store.paths import daily_journal_path


SCHEMA_VERSION = 1


def _block_seconds(*, start: datetime, end: datetime) -> int:
    # Derived field for humans: never negative.
    return max(0, int((end - start).total_seconds()))


def _block_to_dict(
    block: Block, *, now_wall: datetime | None = None, open_block: bool = False
) -> dict:
    end = block.end
    if end is None and now_wall is not None:
        end = now_wall

    seconds = _block_seconds(start=block.start, end=end) if end is not None else None

    out = {
        "type": block.type.value,
        "start": block.start.isoformat(),
        # For open blocks we persist a checkpoint end; for closed blocks this is the true end.
        "end": end.isoformat() if end is not None else None,
        "seconds": seconds,
    }

    if open_block:
        out["open"] = True

    return out


def _block_from_dict(raw: dict) -> Block:
    # Ignore derived fields like `seconds`; they are recomputed.
    return Block(
        type=State(raw["type"]),
        start=datetime.fromisoformat(raw["start"]),
        end=datetime.fromisoformat(raw["end"]) if raw.get("end") else None,
    )


def load_day(*, day: date) -> BlockManager | None:
    path = daily_journal_path(day)
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    blocks_raw = raw.get("blocks")
    if not isinstance(blocks_raw, list):
        return None

    blocks: list[Block] = []

    for item in blocks_raw:
        if not isinstance(item, dict):
            continue
        block = _block_from_dict(item)

        # If the file was checkpointing an open block, it will have an `end`.
        # On resume we treat it as closed at that last checkpoint to create an implicit gap.
        blocks.append(block)

    manager = BlockManager()
    manager.load(blocks=blocks, current_block=None)
    return manager


def write_day_atomic(*, day: date, config: Config, manager: BlockManager) -> Path:
    path = daily_journal_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)

    now_wall = datetime.now().astimezone()

    blocks: list[dict] = [_block_to_dict(b) for b in manager.blocks]
    current_block = manager.get_current_block()
    if current_block is not None:
        blocks.append(_block_to_dict(current_block, now_wall=now_wall, open_block=True))

    totals = manager.get_totals()
    tz = now_wall.tzinfo

    payload = {
        "schema_version": SCHEMA_VERSION,
        "app": {"name": "idle-ledger", "version": "0.1.0"},
        "date": day.isoformat(),
        "timezone": str(tz) if tz is not None else None,
        "threshold_seconds": config.threshold_seconds,
        "treat_inhibitor_as_activity": config.treat_inhibitor_as_activity,
        "blocks": blocks,
        "totals": {
            "activity_seconds": totals.activity_seconds,
            "break_seconds": totals.break_seconds,
        },
    }

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    with tmp_path.open("w", encoding="utf-8") as f:
        f.write(text)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, path)
    return path
