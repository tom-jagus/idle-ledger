from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Empty, Queue
from threading import Event, Thread


class SleepEventKind(Enum):
    SUSPEND = "suspend"
    RESUME = "resume"


@dataclass(frozen=True)
class SleepEvent:
    kind: SleepEventKind
    when: datetime


class SleepWatcher:
    def __init__(self):
        self._queue: Queue[SleepEvent] = Queue()
        self._thread: Thread | None = None
        self._started = False
        self._ready = Event()
        self._available = False
        self._last_error: str | None = None

    def start(self) -> bool:
        if self._started:
            return self._available

        self._started = True
        self._thread = Thread(target=self._run, name="idle-ledger-sleep", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return self._available

    def is_available(self) -> bool:
        return self._available

    def last_error(self) -> str | None:
        return self._last_error

    def drain(self) -> list[SleepEvent]:
        events: list[SleepEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        return events

    def _run(self) -> None:
        try:
            asyncio.run(self._listen())
        except Exception as exc:
            self._last_error = str(exc)
            self._available = False
            self._ready.set()

    async def _listen(self) -> None:
        try:
            from dbus_next.aio import MessageBus
            from dbus_next.constants import BusType
        except Exception as exc:
            self._last_error = f"dbus import failed: {exc}"
            self._available = False
            self._ready.set()
            return

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        introspection = await bus.introspect("org.freedesktop.login1", "/org/freedesktop/login1")
        obj = bus.get_proxy_object(
            "org.freedesktop.login1", "/org/freedesktop/login1", introspection
        )
        manager = obj.get_interface("org.freedesktop.login1.Manager")

        def handler(sleeping: bool) -> None:
            kind = SleepEventKind.SUSPEND if sleeping else SleepEventKind.RESUME
            self._queue.put(SleepEvent(kind=kind, when=datetime.now().astimezone()))

        manager.on_prepare_for_sleep(handler)  # type: ignore[attr-defined]
        self._available = True
        self._ready.set()
        await asyncio.get_running_loop().create_future()
