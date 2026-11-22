"""The one place the API gets the time from.

Every business time (24 h windows, pause end, consent revocation, event log) comes from
`CLOCK.now()` in main.py. Two adapters satisfy the same interface:

* ShiftedClock: real time plus an offset. Production runs with offset 0; the demo
  "skip time" button advances the offset, and "Reset demo" sets it back to 0.
  Stored data is never rewritten to simulate time passing.
* ManualClock: time that only moves when the caller moves it. Tests and the scripted
  red team use it to replay several days in seconds, so the host never has to trust a
  timestamp sent by a client.

Latency and the engine timeout are measured with real monotonic time, not with a Clock.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))   # Kazakhstan (UTC+5)


class ShiftedClock:
    def __init__(self) -> None:
        self.offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now(TZ) + self.offset

    def advance(self, delta: timedelta) -> None:
        self.offset += delta

    def reset(self) -> None:
        self.offset = timedelta(0)


class ManualClock:
    def __init__(self, start: datetime) -> None:
        self._now = start if start.tzinfo else start.replace(tzinfo=TZ)

    def now(self) -> datetime:
        return self._now

    def set(self, at: datetime) -> None:
        self._now = at if at.tzinfo else at.replace(tzinfo=TZ)

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def reset(self) -> None:
        """Manual time belongs to the caller, so a demo reset leaves it where it is."""
