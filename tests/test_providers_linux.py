import os
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import time

import pytest

from idle_ledger.providers.linux import LinuxProvider
from idle_ledger.engine.types import State


def test_provider_get_user_from_env():
    provider = LinuxProvider()
    os.environ["USER"] = "testuser"
    user = provider._get_user()
    assert user == "testuser"
    del os.environ["USER"]


def test_provider_get_user_fallback():
    provider = LinuxProvider()
    user = provider._get_user()
    assert isinstance(user, str)


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_active(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = """SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE
      1 1000 test  seat0  1131   user    tty1 no   -
      2 1000 test  -     1135   manager -    no   -"""
    mock_run.return_value = mock_result

    provider = LinuxProvider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        mock_props.side_effect = [
            {"State": "active"},
            {"State": "active"},
        ]
        session_id = provider._find_session_id()
        assert session_id == "1"


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_fallback(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = """SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE
      1 1000 test  seat0  1131   user    tty1 no   -"""
    mock_run.return_value = mock_result

    provider = LinuxProvider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        mock_props.return_value = {"State": "inactive"}
        session_id = provider._find_session_id()
        assert session_id == "1"


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_none_found(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = """SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE
      1 1000 other  seat0  1131   user    tty1 no   -"""
    mock_run.return_value = mock_result

    provider = LinuxProvider()
    provider._user = "test"
    session_id = provider._find_session_id()
    assert session_id is None


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_find_session_id_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")

    provider = LinuxProvider()
    provider._user = "test"
    session_id = provider._find_session_id()
    assert session_id is None


def test_provider_get_session_properties():
    provider = LinuxProvider()

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
    provider = LinuxProvider()

    with patch("idle_ledger.providers.linux.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")
        props = provider._get_session_properties("2")
        assert props == {}


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_get_snapshot_idle_zero(mock_run):
    mock_run.return_value = MagicMock(
        stdout="SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE\n      2 1000 test  -     1135   manager -    no   -"
    )

    provider = LinuxProvider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
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
        assert snapshot.provider_meta["session_id"] == "2"


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_get_snapshot_idle_active(mock_run):
    mock_run.return_value = MagicMock(
        stdout="SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE\n      2 1000 test  -     1135   manager -    no   -"
    )

    provider = LinuxProvider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        with patch("idle_ledger.providers.linux.time.monotonic") as mock_mono:
            now_mono = 100000.0
            idle_since = 99700.0
            mock_mono.return_value = now_mono

            mock_props.return_value = {
                "State": "active",
                "IdleHint": "yes",
                "IdleSinceHintMonotonic": str(idle_since),
                "LockedHint": "no",
            }

            snapshot = provider.get_snapshot()
            assert snapshot.idle_seconds == int(now_mono - idle_since)
            assert snapshot.locked is False


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_get_snapshot_locked(mock_run):
    mock_run.return_value = MagicMock(
        stdout="SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE\n      2 1000 test  -     1135   manager -    no   -"
    )

    provider = LinuxProvider()
    provider._user = "test"

    with patch.object(provider, "_get_session_properties") as mock_props:
        mock_props.return_value = {
            "State": "active",
            "IdleHint": "no",
            "IdleSinceHintMonotonic": "0",
            "LockedHint": "yes",
        }

        snapshot = provider.get_snapshot()
        assert snapshot.locked is True


@patch("idle_ledger.providers.linux.subprocess.run")
def test_provider_get_snapshot_no_session(mock_run):
    mock_run.return_value = MagicMock(
        stdout="SESSION  UID USER SEAT  LEADER CLASS   TTY  IDLE SINCE\n      1 1000 other  seat0  1131   user    tty1 no   -"
    )

    provider = LinuxProvider()
    provider._user = "test"

    snapshot = provider.get_snapshot()
    assert snapshot.idle_seconds is None
    assert snapshot.locked is None
    assert snapshot.provider_meta.get("error") == "no_session_found"
