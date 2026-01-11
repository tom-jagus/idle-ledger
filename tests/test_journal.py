import json
from datetime import date, datetime

from idle_ledger.engine.blocks import BlockManager
from idle_ledger.engine.types import Config, State
from idle_ledger.store.journal import write_day_atomic


def test_journal_writes_seconds_per_block(tmp_path, monkeypatch):
    # Force journal path into tmp dir by monkeypatching XDG_DATA_HOME.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    bm = BlockManager()
    now = datetime.now().astimezone()
    bm.transition(State.ACTIVITY, now)

    day = date.today()
    path = write_day_atomic(day=day, config=Config(), manager=bm)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["blocks"][0]["type"] == "activity"
    assert raw["blocks"][0].get("open") is True
    assert raw["blocks"][0].get("end") is not None
    assert "seconds" in raw["blocks"][0]
    assert isinstance(raw["blocks"][0]["seconds"], int)
    assert raw["blocks"][0]["seconds"] >= 0
