"""
analog.py – analoge Werte von Sticks und Triggern alltagstauglich machen.

  normalize / normalize_trigger   Rohwert -> -1..1 bzw. 0..1
  deadzone_axial                  Deadzone je Achse (Kreuzform)
  deadzone_radial                 Deadzone als Kreis um die Mitte
  curve                           Kennlinie: feinfühlig in der Mitte, schnell am Rand
  polar / stick_angle             Stick -> Winkel und Auslenkung
  stick_to_hue                    Stick als Farbkreis (0° = oben, im Uhrzeigersinn)
  StickDirection                  Stick -> UP/DOWN/LEFT/RIGHT/CENTER mit Hysterese
  TriggerSwitch                   analoger Trigger -> Taste mit Hysterese
  Quantizer                       Werte auf Raster runden, kleine Änderungen verwerfen
  RateLimiter                     höchstens n Werte pro Sekunde
  ChangeFilter                    nur senden, wenn sich etwas geändert hat
"""

from __future__ import annotations

import math
import time
from typing import Callable, Dict, Hashable, Optional, Tuple


# -- Normalisierung --------------------------------------------------------------
def clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def normalize(raw: float, lo: float, hi: float, invert: bool = False) -> float:
    """Rohwert im Bereich lo..hi -> -1..1 (Mitte = 0)."""
    if hi == lo:
        return 0.0
    v = clamp(2.0 * (raw - lo) / (hi - lo) - 1.0)
    return -v if invert else v


def normalize_trigger(raw: float, lo: float, hi: float) -> float:
    """Rohwert lo (losgelassen) .. hi (durchgedrückt) -> 0..1."""
    if hi == lo:
        return 0.0
    return clamp((raw - lo) / (hi - lo), 0.0, 1.0)


# -- Deadzone und Kennlinie ------------------------------------------------------
def deadzone_axial(v: float, dz: float = 0.15) -> float:
    """Werte |v| < dz werden 0; der Rest wird wieder auf 0..1 gestreckt."""
    if abs(v) < dz:
        return 0.0
    return math.copysign((abs(v) - dz) / (1.0 - dz), v)


def deadzone_radial(x: float, y: float, dz: float = 0.15) -> Tuple[float, float]:
    """Deadzone als Kreis: Richtung bleibt erhalten, Betrag wird gestreckt."""
    r = math.hypot(x, y)
    if r < dz:
        return 0.0, 0.0
    scale = min(1.0, (r - dz) / (1.0 - dz)) / r
    return x * scale, y * scale


def curve(v: float, exponent: float = 2.0) -> float:
    """Kennlinie |v|^exponent mit Vorzeichen; exponent 1 = linear."""
    return math.copysign(abs(v) ** exponent, v)


# -- Stick als Winkel --------------------------------------------------------------
def polar(x: float, y: float) -> Tuple[float, float]:
    """(x, y) -> (Winkel in Grad, Betrag). 0° = oben, im Uhrzeigersinn, 0..360."""
    angle = (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
    return angle, min(1.0, math.hypot(x, y))


def stick_to_hue(x: float, y: float, dz: float = 0.5, step: int = 5,
                 offset: float = 0.0) -> Optional[int]:
    """
    Stick als Farbkreis: Richtung = Farbton. Liefert None, solange der Stick
    nicht weit genug ausgelenkt ist (sonst springt die Farbe beim Loslassen).
    step rundet auf ein Raster (5° -> 72 Farben).
    """
    angle, r = polar(x, y)
    if r < dz:
        return None
    hue = (angle + offset) % 360.0
    return int(round(hue / step) * step) % 360


class StickDirection:
    """
    Stick -> Richtung (UP, DOWN, LEFT, RIGHT, CENTER) mit Hysterese.
    Eine Richtung gilt ab 'on' (0.6) und endet erst unter 'off' (0.4).
    update() liefert die neue Richtung nur bei einem Wechsel, sonst None.
    """

    def __init__(self, on: float = 0.6, off: float = 0.4):
        self.on, self.off = on, off
        self.direction = "CENTER"

    def update(self, x: float, y: float) -> Optional[str]:
        _, r = polar(x, y)
        if self.direction == "CENTER":
            if r < self.on:
                return None
            self.direction = self._classify(x, y)
            return self.direction
        if r <= self.off:
            self.direction = "CENTER"
            return "CENTER"
        new = self._classify(x, y)
        if new != self.direction and r >= self.on:   # Richtungswechsel ohne Mitte
            self.direction = new
            return new
        return None

    @staticmethod
    def _classify(x: float, y: float) -> str:
        if abs(x) > abs(y):
            return "RIGHT" if x > 0 else "LEFT"
        return "UP" if y > 0 else "DOWN"


class TriggerSwitch:
    """
    Analoger Trigger -> Taste. Hysterese verhindert Flattern um die Schwelle:
    gedrückt ab 'on', losgelassen erst unter 'off'.
    update() liefert True (gedrückt) / False (losgelassen) nur bei einem Wechsel.
    """

    def __init__(self, on: float = 0.6, off: float = 0.4):
        if off >= on:
            raise ValueError("off muss kleiner als on sein")
        self.on, self.off = on, off
        self.pressed = False

    def update(self, value: float) -> Optional[bool]:
        if not self.pressed and value >= self.on:
            self.pressed = True
            return True
        if self.pressed and value <= self.off:
            self.pressed = False
            return False
        return None


# -- Datenrate begrenzen -------------------------------------------------------------
class Quantizer:
    """Wert auf ein Raster runden; nur Änderungen >= min_delta weitergeben."""

    def __init__(self, step: float = 5, min_delta: Optional[float] = None,
                 lo: float = 0, hi: float = 100):
        self.step, self.lo, self.hi = step, lo, hi
        self.min_delta = step if min_delta is None else min_delta
        self.last: Optional[float] = None

    def update(self, value: float) -> Optional[float]:
        q = round(value / self.step) * self.step
        q = max(self.lo, min(self.hi, q))
        if isinstance(self.step, int):
            q = int(q)
        if self.last is not None and abs(q - self.last) < self.min_delta:
            return None
        self.last = q
        return q


class RateLimiter:
    """Höchstens ein Wert je Schlüssel alle 'interval' Sekunden."""

    def __init__(self, interval: float = 0.1, clock: Callable[[], float] = time.monotonic):
        self.interval, self.clock = interval, clock
        self._last: Dict[Hashable, float] = {}

    def allow(self, key: Hashable = None) -> bool:
        now = self.clock()
        if now - self._last.get(key, -1e9) < self.interval:
            return False
        self._last[key] = now
        return True


class ChangeFilter:
    """Nur durchlassen, wenn sich der Wert je Schlüssel geändert hat."""

    def __init__(self, tolerance: float = 0.0):
        self.tolerance = tolerance
        self._last: Dict[Hashable, object] = {}

    def changed(self, key: Hashable, value) -> bool:
        old = self._last.get(key)
        if old is not None and isinstance(value, (int, float)) and isinstance(old, (int, float)):
            if abs(value - old) <= self.tolerance:
                return False
        elif old == value:
            return False
        self._last[key] = value
        return True

    def forget(self, key: Hashable = None) -> None:
        if key is None:
            self._last.clear()
        else:
            self._last.pop(key, None)
