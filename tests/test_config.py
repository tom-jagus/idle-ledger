from pathlib import Path
from tempfile import TemporaryDirectory

from idle_ledger.engine.types import Config
from idle_ledger.store.config import load_config, load_linux_options


def test_load_config_defaults_when_missing():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        cfg, meta = load_config(path, create_if_missing=False)

    assert isinstance(cfg, Config)
    assert meta["loaded"] is False


def test_load_config_parses_values():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        path.write_text(
            "threshold_seconds = 123\n"
            "poll_seconds = 4.5\n"
            "journal_heartbeat_seconds = 10\n"
            "treat_inhibitor_as_activity = false\n"
            "\n"
            "[linux]\n"
            "prefer_hypridle = false\n",
            encoding="utf-8",
        )

        cfg, meta = load_config(path, create_if_missing=False)
        linux = load_linux_options(path)

    assert meta["loaded"] is True
    assert cfg.threshold_seconds == 123
    assert cfg.poll_seconds == 4.5
    assert cfg.journal_heartbeat_seconds == 30
    assert cfg.treat_inhibitor_as_activity is False
    assert linux["prefer_hypridle"] is False
