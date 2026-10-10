"""
source.py – eine Ereignisquelle nach Wahl: echter Controller oder Aufzeichnung.

Alle Programme ab Kapitel 9 akzeptieren dieselben Optionen:
  --replay DATEI     Aufzeichnung abspielen statt Controller (Kapitel 8)
  --speed 1.0        Geschwindigkeit der Aufzeichnung
  --alias NAME       Controller über config.yaml auswählen (Kapitel 12)
  --path /dev/input/eventN
  --backend evdev | pygame | gamecontroller
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import AsyncIterator, Iterator, Optional

from .events import GamepadEvent


def add_source_args(ap: argparse.ArgumentParser) -> None:
    g = ap.add_argument_group("Ereignisquelle")
    g.add_argument("--replay", help="Aufzeichnung (JSON-Zeilen) statt Controller")
    g.add_argument("--speed", type=float, default=1.0, help="Abspielgeschwindigkeit")
    g.add_argument("--alias", help="Controller-Alias aus config.yaml (Abschnitt gamepads)")
    g.add_argument("--path", help="/dev/input/eventN")
    g.add_argument("--backend", choices=["evdev", "pygame", "gamecontroller"], default="evdev")
    g.add_argument("--mapping", help="Mapping-Datei erzwingen (Name oder Pfad)")


def _mapping(args, cfg):
    from .mapping import Mapping
    return Mapping.load(args.mapping) if getattr(args, "mapping", None) else None


def _evdev_pad(args, cfg, pad_name: str):
    from .backends.evdev_backend import EvdevGamepad
    from .devices import find_pad
    from .mapping import find_mapping
    path = args.path
    info = None
    if not path:
        info = find_pad(args.alias, (cfg or {}).get("gamepads") or [])
        if info is None:
            raise SystemExit(f"Kein Gamepad gefunden{' für Alias ' + args.alias if args.alias else ''}.")
        path = info.path
    mapping = _mapping(args, cfg)
    if mapping is None and info is not None:
        dirs = [Path(d) for d in (cfg or {}).get("mapping_dirs", []) if Path(d).is_dir()]
        mapping = find_mapping(info.name, info.vendor, info.product, dirs)
    return EvdevGamepad(path, mapping, pad=pad_name)


def open_source(args, cfg: Optional[dict] = None) -> "EventSource":
    pad_name = args.alias or "pad0"
    if args.replay:
        return EventSource(replay=args.replay, speed=args.speed, pad_name=pad_name)
    if args.backend == "evdev":
        return EventSource(pad=_evdev_pad(args, cfg, pad_name))
    from .backends.pygame_backend import PygameGamepad
    return EventSource(pad=PygameGamepad(0, _mapping(args, cfg), pad_name,
                                         gamecontroller=args.backend == "gamecontroller"))


class EventSource:
    """Einheitlicher Zugriff: synchron (events) oder mit asyncio (async_events)."""

    def __init__(self, pad=None, replay: Optional[str] = None, speed: float = 1.0,
                 pad_name: str = "pad0"):
        self.pad = pad
        self.replay = replay
        self.speed = speed
        self.pad_name = pad_name
        self.path = getattr(getattr(pad, "device", None), "path", None)   # für LEDs/Akku

    @property
    def name(self) -> str:
        return f"Aufzeichnung {Path(self.replay).name}" if self.replay else self.pad.name

    def events(self) -> Iterator[GamepadEvent]:
        if self.replay:
            from .backends import replay
            yield from replay.play(replay.load(self.replay, self.pad_name), self.speed)
        else:
            yield from self.pad.events()

    async def async_events(self) -> AsyncIterator[GamepadEvent]:
        if self.replay:
            from .backends import replay
            async for ev in replay.async_play(replay.load(self.replay, self.pad_name), self.speed):
                yield ev
        elif hasattr(self.pad, "async_events"):
            async for ev in self.pad.async_events():
                yield ev
        else:                                   # pygame: abfragen, ohne die Schleife zu blockieren
            import asyncio
            while True:
                for ev in self.pad.poll():
                    yield ev
                await asyncio.sleep(0.01)
