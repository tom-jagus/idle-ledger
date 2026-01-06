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

Daily file: `YYYY-MM-DD.json`

Contains:

- totals (`activity_seconds`, `break_seconds`)
- list of blocks with start/end timestamps

Write is **atomic** (temp + fsync + rename). Crash resume continues from today’s file.

## Installation (dev)

This project is intentionally small and boring.

- Python: 3.11+ (target)
- Packaging: TBD (uv/poetry/pip) — keep it simple early

## CLI (planned)

| Command                                       | Purpose                                                    |
| --------------------------------------------- | ---------------------------------------------------------- |
| `idle-ledger debug`                           | Print live snapshot + derived state + totals (Linux first) |
| `idle-ledger run`                             | Run tracker daemon (headless)                              |
| `idle-ledger summarize week --week YYYY-WW`   | Generate weekly summary JSON                               |
| `idle-ledger summarize month --month YYYY-MM` | Generate monthly summary JSON                              |
| `idle-ledger export csv --range ...`          | Optional: export for analysis                              |

## Configuration

Config file (TOML):

- Linux: `~/.config/idle-ledger/config.toml`
- Windows: `%APPDATA%/idle-ledger/config.toml`

Key settings:

- `threshold_seconds` (default 300)
- `poll_seconds` (default 2–5)
- `treat_inhibitor_as_activity` (default true)

## Roadmap

See `MILESTONES.md`. UI (tray icon) is intentionally last.

## License

TBD (MIT recommended for a utility like this).
