import os
import subprocess
from unittest.mock import MagicMock, patch

from idle_ledger.providers.linux import LinuxProvider


def _make_provider() -> LinuxProvider:
    # Keep tests deterministic and isolated from Hyprland/hypridle.
    return LinuxProvider(threshold_seconds=300, prefer_hypridle=False)


def test_provider_get_user_from_env():
    provider = _make_provider()
    os.environ["USER"] = "testuser"
    user = provider._get_user()
    assert user == "testuser"
    del os.environ["USER"]


def test_provider_get_user_fallback():
    provider = _make_provider()
    user = provider._get_user()
    assert isinstance(user, str)


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_active(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "1 1000 test seat0 1131 user tty1\n2 1000 test - 1135 manager -"
    mock_run.return_value = mock_result

    provider = _make_provider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        mock_props.side_effect = [
            {"State": "active"},
            {"State": "inactive"},
        ]
        session_id = provider._find_session_id()
        assert session_id == "1"


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_fallback(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "1 1000 test seat0 1131 user tty1"
    mock_run.return_value = mock_result

    provider = _make_provider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        mock_props.return_value = {"State": "inactive"}
        session_id = provider._find_session_id()
        assert session_id == "1"


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_none_found(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "1 1000 other seat0 1131 user tty1"
    mock_run.return_value = mock_result

    provider = _make_provider()
    provider._user = "test"
    session_id = provider._find_session_id()
    assert session_id is None


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")

    provider = _make_provider()
    provider._user = "test"
    session_id = provider._find_session_id()
    assert session_id is None


def test_provider_get_session_properties():
    provider = _make_provider()

    with patch("idle_ledger.providers.linux.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "State=active\nIdleHint=no\nIdleSinceHintMonotonic=0\nLockedHint=no"
        mock_run.return_value = mock_result

        props = provider._get_session_properties("2")
        assert props == {
            "State": "active",
            "IdleHint": "no",
            "IdleSinceHintMonotonic": "0",
            "LockedHint": "no",
        }


def test_provider_get_session_properties_error():
    provider = _make_provider()

    with patch("idle_ledger.providers.linux.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")
        props = provider._get_session_properties("2")
        assert props == {}


def test_provider_get_snapshot_idle_zero():
    provider = _make_provider()
    provider._user = "test"
    provider._session_id = "2"

    with patch.object(provider, "_get_inhibited") as mock_inhib:
        with patch.object(provider, "_get_session_properties") as mock_props:
            mock_inhib.return_value = None
            mock_props.return_value = {
                "State": "active",
                "IdleHint": "no",
                "IdleSinceHintMonotonic": "0",
                "LockedHint": "no",
            }

            snapshot = provider.get_snapshot()
            assert snapshot.idle_seconds == 0
            assert snapshot.locked is False
            assert snapshot.inhibited is None
            assert (snapshot.provider_meta or {}).get("session_id") == "2"


def test_provider_get_snapshot_idle_active():
    provider = _make_provider()
    provider._user = "test"
    provider._session_id = "2"

    with patch.object(provider, "_get_inhibited") as mock_inhib:
        with patch.object(provider, "_get_session_properties") as mock_props:
            with patch("idle_ledger.providers.linux.time.monotonic") as mock_mono:
                now_mono = 100_000.0
                idle_since_mono = 99_700.0
                mock_mono.return_value = now_mono

                mock_inhib.return_value = None
                mock_props.return_value = {
                    "State": "active",
                    "IdleHint": "yes",
                    "IdleSinceHintMonotonic": str(int(idle_since_mono * 1_000_000)),
                    "LockedHint": "no",
                }

                snapshot = provider.get_snapshot()
                assert snapshot.idle_seconds == int(now_mono - idle_since_mono)
                assert snapshot.locked is False


def test_provider_get_snapshot_locked():
    provider = _make_provider()
    provider._user = "test"
    provider._session_id = "2"

    with patch.object(provider, "_get_inhibited") as mock_inhib:
        with patch.object(provider, "_get_session_properties") as mock_props:
            mock_inhib.return_value = None
            mock_props.return_value = {
                "State": "active",
                "IdleHint": "no",
                "IdleSinceHintMonotonic": "0",
                "LockedHint": "yes",
            }

            snapshot = provider.get_snapshot()
            assert snapshot.locked is True


def test_provider_get_snapshot_no_session():
    provider = _make_provider()
    provider._user = "test"
    provider._session_id = None

    with patch.object(provider, "_find_session_id") as mock_find:
        mock_find.return_value = None
        snapshot = provider.get_snapshot()

    assert snapshot.idle_seconds is None
    assert snapshot.locked is None
    assert (snapshot.provider_meta or {}).get("error") == "no_session_found"
