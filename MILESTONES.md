# idle-ledger — Milestones

This file exists to prevent scope drift. If an idea isn’t in a milestone, it doesn’t get built.

---

## Phase 0 — Repo + Spec (Foundation)

**Deliverables**

- `SPEC.md` locked and versioned
- `README.md` and `MILESTONES.md`
- Basic project layout:
  - `idle_ledger/engine/`
  - `idle_ledger/providers/`
  - `idle_ledger/store/`
  - `idle_ledger/cli/`
  - `tests/`

**Exit criteria**

- Spec covers state machine, rollover, persistence, summaries

---

## Phase 1 — Linux Debug Runner (Wayland-first)

**Goal**
Prove we can read signals and classify state on your current Linux setup.

**Deliverables**

- `idle-ledger debug`:
  - prints: `idle_seconds`, `locked`, `inhibited`, `state`, totals
  - prints reason for decision
- Provider MVP using:
  - `loginctl` for session hints
  - `systemd-inhibit --list` for inhibitors

**Exit criteria**

- You can run it for a day and the output matches reality closely enough
- You can identify misclassifications and tune rules/config

---

## Phase 2 — Minimal Transition Logging (Don’t skip)

**Goal**
Stop guessing. Persist evidence.

**Deliverables**

- Append-only transition log written on every state change
- Includes: timestamp, prev->next state, idle, locked, inhibited, reason

**Exit criteria**

- Logs survive restarts
- Logs explain every block split

---

## Phase 3 — Atomic Daily JSON + Crash Resume

**Deliverables**

- Daily file `YYYY-MM-DD.json` with blocks + totals
- Atomic writer (temp + fsync + rename)
- Resume from today’s file:
  - continue open block
  - recompute totals from blocks

**Exit criteria**

- Kill the process mid-day -> restart -> no corrupt file, no lost blocks
- Totals match sum of blocks

---

## Phase 4 — Config (TOML) + Validation

**Deliverables**

- `config.toml` support with defaults
- Validation + sane error messages
- Configurable:
  - `threshold_seconds`
  - `poll_seconds`
  - `treat_inhibitor_as_activity`
  - (optional) `min_break_seconds`

**Exit criteria**

- Changes take effect without code edits
- Bad config fails clearly

---

## Phase 5 — Windows Provider (Reuse Engine)

**Deliverables**

- Windows provider for:
  - idle seconds (GetLastInputInfo)
  - locked/session state (minimum viable)
- `idle-ledger debug` works on Windows

**Exit criteria**

- Same engine produces consistent block behavior on Windows
- Daily JSON format identical across platforms

---

## Phase 6 — Summaries + Scheduling

**Deliverables**

- CLI:
  - `summarize week`
  - `summarize month`
- Summary JSON outputs generated from daily files
- Example schedulers:
  - Linux systemd user timer examples (Monday + 1st day)
  - Windows Task Scheduler instructions (call CLI)

**Exit criteria**

- Summaries generate correctly even if the tracker was off for days
- Re-running summary is idempotent (same inputs -> same outputs)

---

## Phase 7 — Optional UI (Tray) “Dessert”

**Deliverables**

- Tray icon (if environment supports it)
- Tooltip shows:
  - today activity time
  - today break time
  - current state
- Menu actions (optional):
  - open today JSON
  - open data directory
  - exit

**Exit criteria**

- UI never becomes a hard dependency for tracking
- Tracking runs headless without GUI components

---

## Explicit Out-of-Scope (until a future version)

- App/window tracking
- Cloud sync
- Productivity scoring
- Database storage
- Fancy dashboards (export CSV later if needed)
