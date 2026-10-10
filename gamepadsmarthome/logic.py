"""
logic.py – aus rohen Tastendrücken wird Bedienlogik.

Ein Gamepad hat nur gut ein Dutzend Tasten. Damit sie für ein ganzes Haus reichen,
unterscheiden wir, WIE eine Taste gedrückt wird:

  press     Taste gedrückt (sofort)
  release   Taste losgelassen
  short     kurz gedrückt und losgelassen
  long      länger als long_press gehalten (einmal, noch während des Haltens)
  double    zweimal kurz hintereinander (zusätzlich zum zweiten short)
  repeat    gehalten: wiederholt sich wie eine Taste auf der Tastatur
            (nur für die Steuerelemente in 'repeat', etwa das Steuerkreuz)

Das Steuerkreuz wird zu vier Tasten up/down/left/right, die Trigger lt/rt werden
mit Hysterese zu Tasten, und die Sticks liefern Richtungen:
  lstick:up, lstick:left ..., lstick:center   (ebenso rstick)

Ebenen: Ist eine Taste aus 'modifiers' gehalten (z. B. lb), heißt eine zweite Taste
"lb+a" statt "a" – die Belegung verdoppelt sich. Die Ebenentaste selbst löst dann
beim Loslassen kein short aus.

Die Zeit kommt von außen (Ereigniszeit bzw. tick(now)) – so bleibt alles testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .analog import StickDirection, TriggerSwitch
from .events import GamepadEvent

DIRECTIONS = {(0, 1): "up", (0, -1): "down", (-1, 0): "left", (1, 0): "right"}


@dataclass(frozen=True)
class Gesture:
    control: str
    gesture: str
    pad: str = "pad0"
    t: float = 0.0

    def __str__(self) -> str:
        return f"{self.control}:{self.gesture}"


class _Key:
    __slots__ = ("pressed", "t0", "full", "long", "repeated", "next_repeat", "last_short", "used")

    def __init__(self) -> None:
        self.pressed = False
        self.t0 = 0.0
        self.full = ""
        self.long = False
        self.repeated = False
        self.next_repeat: Optional[float] = None
        self.last_short = -1e9
        self.used = False


def _directions(v: Tuple[int, int]) -> set:
    x, y = v
    out = set()
    if y > 0:
        out.add("up")
    if y < 0:
        out.add("down")
    if x < 0:
        out.add("left")
    if x > 0:
        out.add("right")
    return out


class ControlLogic:
    """Bedienlogik für EINEN Controller."""

    def __init__(self, long_press: float = 0.6, double_press: float = 0.3,
                 repeat_delay: float = 0.4, repeat_interval: float = 0.15,
                 repeat: Iterable[str] = ("up", "down", "left", "right"),
                 modifiers: Iterable[str] = (), trigger_on: float = 0.6,
                 trigger_off: float = 0.4, stick_on: float = 0.6, stick_off: float = 0.4,
                 pad: str = "pad0"):
        self.long_press, self.double_press = long_press, double_press
        self.repeat_delay, self.repeat_interval = repeat_delay, repeat_interval
        self.repeat = set(repeat)
        self.modifiers = list(modifiers)
        self.pad = pad
        self.keys: Dict[str, _Key] = {}
        self.triggers = {n: TriggerSwitch(trigger_on, trigger_off) for n in ("lt", "rt")}
        self.sticks = {n: StickDirection(stick_on, stick_off) for n in ("lstick", "rstick")}
        self.stick_xy = {"lstick": [0.0, 0.0], "rstick": [0.0, 0.0]}
        self.dpad = (0, 0)

    @classmethod
    def from_config(cls, cfg: Optional[dict], pad: str = "pad0") -> "ControlLogic":
        cfg = dict(cfg or {})
        return cls(pad=pad, **cfg)

    def _key(self, name: str) -> _Key:
        return self.keys.setdefault(name, _Key())

    # -- Eingang -------------------------------------------------------------------
    def feed(self, ev: GamepadEvent) -> List[Gesture]:
        out: List[Gesture] = []
        t = ev.t
        if ev.kind == "button":
            (self._press if ev.value else self._release)(ev.control, t, out)
        elif ev.kind == "dpad":
            before, after = _directions(self.dpad), _directions(ev.value)  # type: ignore[arg-type]
            self.dpad = ev.value  # type: ignore[assignment]
            for d in sorted(before - after):
                self._release(d, t, out)
            for d in sorted(after - before):
                self._press(d, t, out)
        elif ev.kind == "axis":
            if ev.control in self.triggers:
                state = self.triggers[ev.control].update(float(ev.value))
                if state is True:
                    self._press(ev.control, t, out)
                elif state is False:
                    self._release(ev.control, t, out)
            else:
                stick = "lstick" if ev.control in ("lx", "ly") else "rstick"
                xy = self.stick_xy[stick]
                xy[0 if ev.control[1] == "x" else 1] = float(ev.value)
                direction = self.sticks[stick].update(xy[0], xy[1])
                if direction:
                    out.append(Gesture(stick, direction.lower(), self.pad, t))
        return out

    def tick(self, now: float) -> List[Gesture]:
        """Regelmäßig aufrufen (z. B. alle 20 ms): erzeugt long und repeat."""
        out: List[Gesture] = []
        for name, k in self.keys.items():
            if not k.pressed:
                continue
            if name in self.repeat:
                while k.next_repeat is not None and now >= k.next_repeat:
                    out.append(Gesture(k.full, "repeat", self.pad, k.next_repeat))
                    k.repeated = True
                    k.next_repeat += self.repeat_interval
            elif not k.long and now - k.t0 >= self.long_press:
                k.long = True
                out.append(Gesture(k.full, "long", self.pad, now))
        return out

    # -- intern ------------------------------------------------------------------------
    def _press(self, name: str, t: float, out: List[Gesture]) -> None:
        k = self._key(name)
        if k.pressed:
            return
        held = [m for m in self.modifiers if m != name and self._key(m).pressed]
        for m in held:
            self._key(m).used = True
        k.pressed, k.t0, k.long, k.repeated, k.used = True, t, False, False, False
        k.full = "+".join(held + [name])
        k.next_repeat = t + self.repeat_delay if name in self.repeat else None
        out.append(Gesture(k.full, "press", self.pad, t))

    def _release(self, name: str, t: float, out: List[Gesture]) -> None:
        k = self._key(name)
        if not k.pressed:
            return
        k.pressed = False
        out.append(Gesture(k.full, "release", self.pad, t))
        if k.used or k.long or k.repeated:      # Ebenentaste, langer Druck, Wiederholung
            return
        out.append(Gesture(k.full, "short", self.pad, t))
        if t - k.last_short <= self.double_press:
            out.append(Gesture(k.full, "double", self.pad, t))
            k.last_short = -1e9
        else:
            k.last_short = t


class Ring:
    """Endlose Auswahlliste – etwa Räume oder Radiosender."""

    def __init__(self, entries: Sequence[str], start: int = 0):
        if not entries:
            raise ValueError("Ring braucht mindestens einen Eintrag")
        self.entries = list(entries)
        self.index = start % len(self.entries)

    @property
    def current(self) -> str:
        return self.entries[self.index]

    def next(self) -> str:
        self.index = (self.index + 1) % len(self.entries)
        return self.current

    def prev(self) -> str:
        self.index = (self.index - 1) % len(self.entries)
        return self.current

    def select(self, entry: str) -> str:
        self.index = self.entries.index(entry)
        return self.current
