"""
evdev_backend.py – Gamepads direkt über die Linux-Eingabeschnittstelle lesen.

EvdevTranslator   (type, code, value) -> GamepadEvent   (ohne Hardware testbar)
EvdevGamepad      ein Gerät öffnen und Ereignisse liefern (synchron oder asyncio)

Der Treiber legt für jedes Gerät eine Datei /dev/input/eventN an. Jede Meldung
besteht aus Typ (EV_KEY, EV_ABS ...), Code (BTN_SOUTH, ABS_X ...) und Wert.
EV_SYN trennt zusammengehörige Meldungen – wir brauchen es nicht.
"""

from __future__ import annotations

import time
from typing import AsyncIterator, Dict, Iterator, List, Optional, Tuple

from .. import codes as C
from ..analog import normalize, normalize_trigger
from ..events import GamepadEvent
from ..mapping import Mapping, find_mapping
from .base import DpadState, collect


class EvdevTranslator:
    """Übersetzt Rohmeldungen eines Geräts mit Hilfe einer Mapping-Datei."""

    def __init__(self, mapping: Mapping, absinfo: Optional[Dict[int, Tuple[int, int]]] = None,
                 pad: str = "pad0"):
        self.map = mapping.evdev
        self.absinfo = absinfo or {}           # Code -> (min, max) laut Treiber
        self.pad = pad
        self.dpad = DpadState()

    def _range(self, code: int, lo: Optional[float], hi: Optional[float]) -> Tuple[float, float]:
        dlo, dhi = self.absinfo.get(code, (-32768, 32767))
        return (dlo if lo is None else lo), (dhi if hi is None else hi)

    def translate(self, etype: int, code: int, value: int,
                  t: Optional[float] = None) -> List[GamepadEvent]:
        t = time.monotonic() if t is None else t
        out: List[GamepadEvent] = []
        if etype == C.EV_KEY:
            if value == 2:                           # Tastenwiederholung des Kernels
                return out
            if code in self.map.buttons:
                out.append(GamepadEvent("button", self.map.buttons[code], int(bool(value)), self.pad, t))
            elif code in self.map.dpad_buttons:
                new = self.dpad.set_button(self.map.dpad_buttons[code], bool(value))
                if new is not None:
                    out.append(GamepadEvent("dpad", "dpad", new, self.pad, t))
        elif etype == C.EV_ABS:
            hat = self.map.hat
            if hat is not None and code in hat:
                axis = "x" if code == hat[0] else "y"
                # evdev: oben = -1, wir wollen oben = +1
                collect(out, self._dpad_event(self.dpad.set_axis(axis, value if axis == "x" else -value), t))
            elif code in self.map.axes:
                spec = self.map.axes[code]
                lo, hi = self._range(code, spec.lo, spec.hi)
                v = normalize_trigger(value, lo, hi) if spec.trigger else normalize(value, lo, hi, spec.invert)
                out.append(GamepadEvent("axis", spec.name, round(v, 4), self.pad, t))
        return out

    def _dpad_event(self, new, t) -> Optional[GamepadEvent]:
        return None if new is None else GamepadEvent("dpad", "dpad", new, self.pad, t)


class EvdevGamepad:
    """
    Ein Gamepad über python-evdev öffnen.

        pad = EvdevGamepad("/dev/input/event5")      # Mapping wird automatisch gewählt
        for ev in pad.events():
            print(ev)
    """

    def __init__(self, path: str, mapping: Optional[Mapping] = None, pad: str = "pad0",
                 grab: bool = False):
        from evdev import InputDevice, ecodes  # erst hier: nur unter Linux verfügbar

        self.device = InputDevice(path)
        info = self.device.info
        self.mapping = mapping or find_mapping(self.device.name, info.vendor, info.product)
        absinfo = {}
        for code, ai in self.device.capabilities(absinfo=True).get(ecodes.EV_ABS, []):
            absinfo[code] = (ai.min, ai.max)
        self.translator = EvdevTranslator(self.mapping, absinfo, pad)
        if grab:                     # andere Programme sehen das Gerät dann nicht mehr
            self.device.grab()

    @property
    def name(self) -> str:
        return self.device.name

    # Zeitstempel: time.monotonic() beim Empfang – dieselbe Uhr wie in logic.py
    def events(self) -> Iterator[GamepadEvent]:
        for e in self.device.read_loop():
            yield from self.translator.translate(e.type, e.code, e.value)

    async def async_events(self) -> AsyncIterator[GamepadEvent]:
        async for e in self.device.async_read_loop():
            for ev in self.translator.translate(e.type, e.code, e.value):
                yield ev

    def close(self) -> None:
        try:
            self.device.ungrab()
        except Exception:
            pass
        self.device.close()
