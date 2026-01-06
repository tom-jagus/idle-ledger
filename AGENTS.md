# AGENTS.md — Guide for Agentic Coding Assistants

## Project Overview

`idle-ledger` is an automatic activity/break tracking utility for Linux (Wayland) and Windows. Target Python: 3.14+

**Critical:** SPEC.md is the source of truth. If code contradicts SPEC.md, the code is wrong.

---

## Commands

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
uv pip install -e .
```

### Testing
```bash
pytest                              # All tests
pytest tests/test_engine.py         # Single file
pytest tests/test_engine.py::test_threshold_subtraction  # Specific test
pytest --cov=idle_ledger            # With coverage
```

### Linting & Type Checking
```bash
ruff format .   # Format code
ruff check .    # Lint code
mypy idle_ledger/  # Type check
```

### Running
```bash
python -m idle_ledger.cli debug  # Debug mode
python -m idle_ledger.cli run    # Run tracker daemon
```

---

## Code Style Guidelines

### Philosophy
- Keep it "small and boring" — utility, not a framework
- Platform-specific code in `idle_ledger/providers/`
- Core logic (state machine, persistence) in `idle_ledger/engine/`
- Prefer dataclasses for structured data

### Naming
- Functions/variables: `snake_case` — `get_idle_seconds()`
- Classes: `PascalCase` — `StateEngine`
- Constants: `UPPER_SNAKE_CASE` — `DEFAULT_THRESHOLD_SECONDS`
- Private members: `_leading_underscore`

### Imports Order
1. Standard library (`from datetime import datetime`)
2. Third-party (`from platformdirs import user_data_dir`)
3. Local imports (`from idle_ledger.engine.state import State`)

### Type Hints
- Use `|` for unions: `int | None`
- Always type function signatures
- Use `typing.Final` for constants

### Error Handling
- Providers return `None` for unknown signals (never fake data)
- Use `RuntimeError` for unrecoverable state
- Log warnings for recoverable issues, errors for failures

### Formatting
- Line length: 100 characters (Ruff default)
- Use `ruff format` for auto-formatting
- Prefer f-strings

### File Organization
```
idle_ledger/
├── cli/              # CLI entrypoints
├── engine/           # State machine, persistence
├── providers/        # Platform-specific signals
└── store/            # JSON writer, crash resume, summaries
tests/
```

---

## Key Implementation Rules

### State Machine (SPEC.md Section 4)
Default policy:
1. `locked == True` → BREAK
2. `idle_seconds is None` → ACTIVITY (fail-open)
3. `idle_seconds <= threshold` → ACTIVITY
4. `idle_seconds > threshold`:
   - If `treat_inhibitor_as_activity and inhibited` → ACTIVITY
   - Else → BREAK

**Threshold subtraction:** ACTIVITY→BREAK ends at `last_active + threshold`, not `now`

### Persistence (SPEC.md Section 6)
- Atomic write: temp file → `fsync()` → rename
- Daily file: `YYYY-MM-DD.json` in `user_data_dir("idle-ledger")`
- Config: `config.toml` in `user_config_dir("idle-ledger")`
- Crash resume: load today's file, continue open block, recompute totals

### Time Handling
- Storage: timezone-aware ISO 8601 with offset
- Internal deltas: use `time.monotonic()`
- Day rollover: at local midnight, close block, start new file

---

## Testing Strategy

- **Unit tests:** Pure logic (state transitions, block math)
- **Integration tests:** Provider → engine → persistence
- **Property-based tests (optional):** Invariants like `sum(blocks) == totals`
- Mock providers for cross-platform testing

---

## Non-Goals (Do NOT Implement)

- Keystroke-level logging
- App/website tracking
- Cloud sync
- Productivity scoring
- Database storage (JSON files sufficient)
- Fancy dashboards (export CSV later if needed)

---

## Acceptance Criteria (MVP)

- `idle-ledger debug` reports stable signals/state changes on Linux (Wayland)
- Daily JSON files are atomic and survive `kill -9`
- Resume from today's file without data loss
- Weekly/monthly summaries generate from daily files via CLI

---

## Resources

- **Spec:** SPEC.md (authoritative)
- **Roadmap:** MILESTONES.md
- **Readme:** README.md
