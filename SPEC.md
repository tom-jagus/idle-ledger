# idle-ledger — Specification

> This spec defines behavior. If code contradicts this doc, the code is wrong.

## 1. Purpose

`idle-ledger` tracks **computer presence/activity time** automatically:
- Runs in background
- Detects **ACTIVE** vs **BREAK**
- Stores daily totals and block timeline to a **daily JSON file**
- Survives crashes (resume from today’s file)
- Summaries are generated via CLI and can be scheduled externally (systemd timer / Task Scheduler)

**Important:** This is not a productivity tracker. It measures presence signals, not output quality.

---

## 2. Terms

- **Activity**: Time considered "present at computer" (includes passive use: reading, watching, meetings).
- **Break**: Time considered "away / not present".
- **Threshold**: Idle duration (default `300s`) after which we declare BREAK.
- **Block**: Contiguous time interval labeled `activity` or `break`.
- **Idle**: Seconds since last user input as reported by provider (platform dependent).
- **Locked**: Session locked/screen locked (provider-dependent). Locked forces BREAK.
- **Inhibited**: An "idle inhibitor" is active (Linux), indicating passive activity (e.g., video/call).

---

## 3. Signals (Provider Contract)

The engine does not talk to OS APIs directly. A provider supplies a snapshot:

```py
Snapshot(
  now_wall: datetime,        # timezone-aware local time (for storage/display)
  now_mono: float,           # monotonic seconds (for delta calculations)
  idle_seconds: int | None,  # None if unknown/unavailable
  locked: bool | None,       # None if unknown
  inhibited: bool | None,    # None if unknown/unavailable
  provider_meta: dict        # debugging (session id, raw fields, etc.)
)
```

Provider rules:
- Must not block for long. Engine loop assumes snapshots are cheap.
- Prefer monotonic time for internal deltas to avoid wall-clock jumps.
- If a signal is unknown, return `None`, not fake data.

---

## 4. Decision Logic (State Machine)

States:
- `ACTIVITY`
- `BREAK`

### 4.1 State Determination

Default policy (MVP):
1) If `locked is True` => `BREAK`
2) Else if `idle_seconds is None` => `ACTIVITY` (fail-open; configurable later)
3) Else if `idle_seconds <= threshold_seconds` => `ACTIVITY`
4) Else (`idle_seconds > threshold_seconds`):
   - If `treat_inhibitor_as_activity` and `inhibited is True` => `ACTIVITY`
   - Else => `BREAK`

Rationale:
- Lock is a hard boundary (user not actively present).
- Idle over threshold normally means away.
- Inhibitors keep passive usage from being misclassified as breaks.

### 4.2 Threshold Subtraction Rule (Retroactive Cut)

When transitioning from `ACTIVITY` to `BREAK` due to idle exceeding threshold:

- Let `t = threshold_seconds`
- Let `last_active_wall = now_wall - idle_seconds`
- Break should begin at: `break_start_wall = last_active_wall + t`

The last `t` seconds preceding the break start were **not** truly activity; they are the grace period.
So the current activity block must end at `break_start_wall` (not at `now_wall`).

### 4.3 Transition Rules

Engine maintains a `current_block` open interval.

On each tick:
- Compute desired `next_state` from Snapshot (Section 4.1)
- If `next_state == current_state`: continue (no-op)
- Else:
  - Close current block:
    - `ACTIVITY -> BREAK`:
      - Close activity at `break_start_wall` (retro cut)
      - Open break at `break_start_wall`
    - `BREAK -> ACTIVITY`:
      - Close break at `now_wall`
      - Open activity at `now_wall`

### 4.4 Minimum Break Length (Optional, not MVP)

If a break would be shorter than `min_break_seconds`, merge it into adjacent activity.
Default: disabled.

---

## 5. Time & Day Boundaries

- Storage uses timezone-aware local timestamps (ISO 8601 with offset).
- Internal deltas use monotonic time where relevant.

### 5.1 Day Rollover

At local midnight:
- Close open block at `23:59:59.999...` (implementation may use next day 00:00 boundary precisely).
- Start a new daily file for the new date.
- Open a new block for the new day using current state.

If rollover happens during BREAK, the break continues across files (i.e., it ends in the new day when activity resumes).

If rollover happens during ACTIVITY, ACTIVITY continues across files.

---

## 6. Persistence

### 6.1 File Locations (Defaults)

Use platform-appropriate directories (via `platformdirs` in code).

- Daily data directory:
  - Linux: `$XDG_DATA_HOME/idle-ledger/` (fallback `~/.local/share/idle-ledger/`)
  - Windows: `%LOCALAPPDATA%/idle-ledger/`

- Config directory:
  - Linux: `$XDG_CONFIG_HOME/idle-ledger/` (fallback `~/.config/idle-ledger/`)
  - Windows: `%APPDATA%/idle-ledger/`

### 6.2 Daily Journal JSON File

Filename: `daily-journal/YYYY-MM-DD.json`

Additionally, a per-day transition log is written for diagnostics:
- `transition-logs/YYYY-MM-DD.jsonl`

Schema (v1):

```json
{
  "schema_version": 1,
  "app": { "name": "idle-ledger", "version": "0.1.0-dev" },
  "date": "2026-01-06",
  "timezone": "Europe/Warsaw",
  "threshold_seconds": 300,
  "treat_inhibitor_as_activity": true,
  "blocks": [
    {
      "type": "activity",
      "start": "2026-01-06T08:12:10+01:00",
      "end": "2026-01-06T10:03:55+01:00",
      "seconds": 671...
    },
    {
      "type": "break",
      "start": "2026-01-06T10:03:55+01:00",
      "end": "2026-01-06T10:10:20+01:00",
      "seconds": 385,
      "open": true
    }
  ],
  "totals": {
    "activity_seconds": 14400,
    "break_seconds": 3600
  }
}
```

Rules:
- `totals` are **derived** from `blocks`. Code may store them for convenience but must be able to recompute and validate.
- `seconds` is derived from `start/end`. Store it for fast reads, but validate on write.
- The current/open block is stored with `open: true` and a periodically updated `end` timestamp (journal heartbeat).

### 6.3 Atomic Write

Writes must be atomic to avoid corrupt files on crash/power loss:
1) Write to temp file in same directory (`YYYY-MM-DD.json.tmp`)
2) `flush` + `fsync`
3) `rename`/replace to final filename

### 6.4 Crash Resume

On startup:
- Load today’s journal if it exists
- Do not retroactively guess time while the process was down
- The last stored `end` timestamp (from the heartbeat) is treated as the last accounted time
- A new block starts at startup time based on the first live snapshot

Result: downtime produces an implicit gap that is not counted as activity or break.

---

## 7. Debug Logging (Required Early)

A lightweight transition log must exist during development:
- Write a line on each transition: timestamp, state change, idle, locked, inhibited.
- Also write a one-time `provider_mode` event on service start (which provider path is active).
- Purpose: validate provider behavior and state machine decisions.

This log is not the “source of truth” for totals; it’s for diagnostics.

---

## 8. Summaries

Summaries are generated from daily journal files, never from running counters.

CLI (MVP):
- `idle-ledger summary` (defaults to today)
- `idle-ledger summary yesterday`
- `idle-ledger summary week`

Formatting:
- Outputs are human-friendly (hours/minutes) and include activity + break totals.
- Daily target minutes are used to show `remaining` / `excess` relative to the target.

---

## 9. Non-Goals (Explicit)

- Keystroke-level logging
- App/website tracking
- Cloud sync
- “Productivity scoring”
- Always-perfect detection across every compositor/environment (providers are swappable)

---

## 10. Acceptance Criteria (MVP)

MVP is considered done when:
- On Linux (Wayland), debug runner reports stable `idle/locked/inhibited` and state changes correctly.
- Daily JSON files are atomic and survive forced termination.
- Resume continues from today’s file without data loss.
- Weekly/monthly summaries are generated from daily files via CLI.
