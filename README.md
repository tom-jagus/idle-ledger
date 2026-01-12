# idle-ledger

Automatic **activity vs break** tracking for Linux (Wayland) and Windows.

It runs in the background, detects when you’re present at the computer (including passive use like reading, videos, meetings), splits your day into `activity` and `break` blocks, and writes an atomic daily JSON ledger you can analyze later.

## What it tracks

- **activity**: time considered “present at computer”
- **break**: time considered “away”
- A break starts when idle exceeds a threshold (default: **5 minutes**)
- The threshold is **retroactively subtracted** from the activity block (grace period)

## What it does NOT do

- Track apps/websites
- Track keystrokes content
- Judge “productivity”

## How it works (high-level)

`idle-ledger` uses a platform-specific **provider** to get a snapshot of:

- idle seconds
- locked/unlocked
- idle inhibitors (Linux)

A shared state machine converts snapshots into `activity`/`break` blocks and persists them to JSON.

## Data output

Base data dir:
- Linux: `~/.local/share/idle-ledger/` (or `$XDG_DATA_HOME/idle-ledger/`)

Files:
- Transition logs: `transition-logs/YYYY-MM-DD.jsonl`
- Daily journal: `daily-journal/YYYY-MM-DD.json`

Contains:

- totals (`activity_seconds`, `break_seconds`)
- list of blocks with start/end timestamps

Write is **atomic** (temp + fsync + rename). Journals are checkpointed periodically so crashes lose at most ~`journal_heartbeat_seconds` of precision.

## Installation (Linux)

User-local install (no venv):

```bash
curl -fsSL https://raw.githubusercontent.com/tom-jagus/idle-ledger/main/install.sh | sh
```

This installs `idle-ledger` into `~/.local/bin/`.

## Installation (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## CLI

| Command             | Purpose |
| ------------------- | ------- |
| `idle-ledger debug`   | Print live snapshot + derived state + totals |
| `idle-ledger run`     | Run tracker loop in foreground (Ctrl+C to stop) |
| `idle-ledger status`  | Show service status + today totals |
| `idle-ledger summary` | Show totals in hours/minutes |

## Configuration

Config file (TOML):

- Linux: `~/.config/idle-ledger/config.toml`
- Windows: `%APPDATA%/idle-ledger/config.toml`

Key settings:

- `threshold_seconds` (default 300)
- `poll_seconds` (default 2.0)
- `journal_heartbeat_seconds` (default 30, min 30)
- `[summary].daily_target_minutes` (default 480)
- `[summary].week_start` (default "iso")
- `treat_inhibitor_as_activity` (default true)

## systemd (user service)

An example unit is included in `systemd/idle-ledger.service`.

```bash
idle-ledger init

# (or, if you want to overwrite an existing unit)
idle-ledger init --force
```

Manual alternative:
```bash
mkdir -p ~/.config/systemd/user
cp systemd/idle-ledger.service ~/.config/systemd/user/idle-ledger.service
systemctl --user daemon-reload
systemctl --user enable --now idle-ledger.service
```

## Roadmap

See `MILESTONES.md`. UI (tray icon) is intentionally last.

## License

TBD (MIT recommended for a utility like this).
