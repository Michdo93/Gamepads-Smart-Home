"""
replay.py – Gamepad-Ereignisse aufzeichnen und wieder abspielen.

Eine Aufzeichnung ist eine Textdatei mit einer JSON-Zeile je Ereignis:

    {"dt": 0.000, "kind": "button", "control": "a", "value": 1}
    {"dt": 0.120, "kind": "button", "control": "a", "value": 0}
    {"dt": 0.500, "kind": "axis",   "control": "rx", "value": 0.82}

dt ist der Abstand zum vorherigen Ereignis in Sekunden. So lassen sich Abläufe im
Labor mit echtem Controller aufnehmen und später ohne Hardware abspielen – etwa in
Tests oder auf dem Entwicklungsrechner.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import AsyncIterator, Iterable, Iterator, List, Optional, TextIO, Union

from ..events import GamepadEvent


def _value(kind: str, value):
    if kind == "dpad":
        return tuple(int(v) for v in value)
    if kind == "button":
        return int(value)
    return float(value)


def load(path: Union[str, Path], pad: Optional[str] = None) -> List[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                row = json.loads(line)
                if pad:
                    row["pad"] = pad
                rows.append(row)
    return rows


def to_events(rows: Iterable[dict], start: float = 0.0) -> List[GamepadEvent]:
    """Aufzeichnung -> Ereignisse mit fortlaufender Zeit (ohne zu warten)."""
    t, out = start, []
    for r in rows:
        t += float(r.get("dt", 0.0))
        out.append(GamepadEvent(r["kind"], r["control"], _value(r["kind"], r["value"]),
                                r.get("pad", "pad0"), t))
    return out


def play(rows: Iterable[dict], speed: float = 1.0) -> Iterator[GamepadEvent]:
    """Aufzeichnung in Echtzeit abspielen (speed 2.0 = doppelt so schnell)."""
    for r in rows:
        if r.get("dt"):
            time.sleep(float(r["dt"]) / speed)
        yield GamepadEvent(r["kind"], r["control"], _value(r["kind"], r["value"]),
                           r.get("pad", "pad0"))


async def async_play(rows: Iterable[dict], speed: float = 1.0) -> AsyncIterator[GamepadEvent]:
    for r in rows:
        if r.get("dt"):
            await asyncio.sleep(float(r["dt"]) / speed)
        yield GamepadEvent(r["kind"], r["control"], _value(r["kind"], r["value"]),
                           r.get("pad", "pad0"))


class Recorder:
    """Ereignisse als JSON-Zeilen schreiben."""

    def __init__(self, fh: TextIO):
        self.fh = fh
        self._last: Optional[float] = None

    def write(self, ev: GamepadEvent) -> None:
        dt = 0.0 if self._last is None else ev.t - self._last
        self._last = ev.t
        value = list(ev.value) if isinstance(ev.value, tuple) else ev.value
        self.fh.write(json.dumps({"dt": round(dt, 3), "kind": ev.kind,
                                  "control": ev.control, "value": value}) + "\n")
        self.fh.flush()
