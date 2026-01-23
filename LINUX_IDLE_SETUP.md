# Linux Idle Detection Setup

## Overview

`idle-ledger` tries to use OS-native signals first and avoids fragile heuristics.

On Hyprland, `systemd-logind` idle hints (`loginctl`) are commonly unreliable, so we prefer `hypridle` when available.

## Detection Priority

1. **hypridle** (Hyprland) — robust Wayland idle detection + respects inhibitors
2. **loginctl** (systemd-logind) — lock state everywhere; idle hints where supported

## hypridle (Hyprland)

### What it does
- `idle-ledger` launches a private `hypridle` instance with a generated config.
- It listens for two events:
  - `timeout` (idle reached the configured threshold)
  - `resume` (activity detected after timeout)

### Why this works well
- Uses `ext-idle-notify-v1` via Hyprland (real Wayland idle)
- Respects DBus/systemd inhibitors by default (video/calls usually prevent idle)

### Requirements
- Running under Hyprland.
- `hypridle` installed and runnable in `$PATH`

Notes:
- When running as a systemd user service, `idle-ledger` will try to auto-detect missing Wayland/Hyprland environment (e.g. `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`) from `$XDG_RUNTIME_DIR`.

## loginctl (systemd-logind)

### What it does
- Reads session properties:
  - `LockedHint` (lock state)
  - `IdleHint` + `IdleSinceHintMonotonic` (idle timing; may be unsupported)

### Notes
- `IdleSinceHintMonotonic` is a monotonic timestamp in **microseconds**.
- On some compositors, `IdleHint` may always report `no`.

## Inhibitors

`idle-ledger` also checks `loginctl list-inhibitors` to detect `WHAT=idle` inhibitors.
When `treat_inhibitor_as_activity=true`, inhibitors keep passive activity (video/calls) from being counted as breaks.
