from .types import Snapshot, Config, State


def classify_state(snapshot: Snapshot, config: Config) -> State:
    """Classify current state from provider snapshot.

    Rules:
        1. If locked is True → BREAK
        2. If idle_seconds is None → ACTIVITY (fail-open)
        3. If idle_seconds <= threshold → ACTIVITY
        4. If idle_seconds > threshold:
           - If treat_inhibitor_as_activity and inhibited → ACTIVITY
           - Else → BREAK

    Args:
        snapshot: Current system snapshot from provider.
        config: Runtime configuration.

    Returns:
        Current state (State.ACTIVITY or State.BREAK).
    """
    if snapshot.locked is True:
        return State.BREAK

    if snapshot.idle_seconds is None:
        return State.ACTIVITY

    if snapshot.idle_seconds <= config.threshold_seconds:
        return State.ACTIVITY

    if config.treat_inhibitor_as_activity and snapshot.inhibited is True:
        return State.ACTIVITY

    return State.BREAK
