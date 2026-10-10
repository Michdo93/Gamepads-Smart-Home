"""
events.py – ein Gamepad-Ereignis unabhängig von Controller und Bibliothek.

Jedes Backend (evdev, pygame, Aufzeichnung) liefert GamepadEvent-Objekte mit
LOGISCHEN Namen. Die Zuordnung Rohcode -> Name steht in der Mapping-Datei des
Controllers (mappings/*.yaml).

  kind     "button" | "axis" | "dpad"
  control  Tasten:   a b x y lb rb back start guide ls rs   (Lage wie beim Xbox-Pad:
                     a = unten, b = rechts, x = links, y = oben)
           Achsen:   lx ly rx ry   -1.0 ... +1.0   (rechts bzw. OBEN positiv)
                     lt rt          0.0 ...  1.0   (losgelassen = 0)
           Steuerkreuz: dpad       (x, y) mit x, y in {-1, 0, 1}, oben = +1
  value    1/0 für Tasten, float für Achsen, Tupel für das Steuerkreuz
  pad      Name des Controllers (Alias aus config.yaml, sonst "pad0")
  t        Zeitpunkt in Sekunden (time.monotonic())
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Tuple, Union

BUTTONS = ("a", "b", "x", "y", "lb", "rb", "back", "start", "guide", "ls", "rs")
STICK_AXES = ("lx", "ly", "rx", "ry")
TRIGGERS = ("lt", "rt")
AXES = STICK_AXES + TRIGGERS
DPAD_DIRECTIONS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}

Value = Union[int, float, Tuple[int, int]]


@dataclass(frozen=True)
class GamepadEvent:
    kind: str
    control: str
    value: Value
    pad: str = "pad0"
    t: float = field(default_factory=time.monotonic, compare=False)

    @property
    def pressed(self) -> bool:
        """Für Tasten: gedrückt? Für das Steuerkreuz: irgendeine Richtung?"""
        if self.kind == "dpad":
            return self.value != (0, 0)
        return bool(self.value)

    def __str__(self) -> str:  # kompakte Ausgabe für das Terminal
        if self.kind == "axis":
            return f"{self.pad:<8} {self.kind:<6} {self.control:<6} {self.value:+.2f}"
        return f"{self.pad:<8} {self.kind:<6} {self.control:<6} {self.value}"


def dpad_name(value: Tuple[int, int]) -> str:
    """(0, 1) -> 'up', (1, -1) -> 'down_right', (0, 0) -> 'none'."""
    x, y = value
    parts = []
    if y > 0:
        parts.append("up")
    elif y < 0:
        parts.append("down")
    if x < 0:
        parts.append("left")
    elif x > 0:
        parts.append("right")
    return "_".join(parts) or "none"
