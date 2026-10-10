"""base.py – Bausteine, die alle Backends gemeinsam nutzen."""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from ..events import GamepadEvent


class DpadState:
    """
    Setzt das Steuerkreuz aus Einzelmeldungen zusammen – egal ob es als Hat
    (x und y getrennt) oder als vier Tasten kommt. Liefert (x, y) nur bei Änderung.
    """

    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self._held: Dict[Tuple[int, int], bool] = {}

    @property
    def value(self) -> Tuple[int, int]:
        return self.x, self.y

    def set_axis(self, axis: str, v: int) -> Optional[Tuple[int, int]]:
        old = self.value
        v = (v > 0) - (v < 0)
        if axis == "x":
            self.x = v
        else:
            self.y = v
        return self.value if self.value != old else None

    def set_button(self, direction: Tuple[int, int], pressed: bool) -> Optional[Tuple[int, int]]:
        old = self.value
        self._held[direction] = pressed
        x = sum(d[0] for d, p in self._held.items() if p)
        y = sum(d[1] for d, p in self._held.items() if p)
        self.x, self.y = max(-1, min(1, x)), max(-1, min(1, y))
        return self.value if self.value != old else None


def emit_changes(events: Iterable[GamepadEvent], last: Dict[str, object],
                 axis_tolerance: float = 0.0) -> Iterator[GamepadEvent]:
    """Nur Ereignisse durchlassen, deren Wert sich geändert hat (Achsen mit Toleranz)."""
    for ev in events:
        key = f"{ev.pad}/{ev.control}"
        old = last.get(key)
        if ev.kind == "axis" and isinstance(old, float):
            if abs(ev.value - old) <= axis_tolerance:  # type: ignore[operator]
                continue
        elif old == ev.value:
            continue
        last[key] = ev.value
        yield ev


def collect(events: List[GamepadEvent], ev: Optional[GamepadEvent]) -> None:
    if ev is not None:
        events.append(ev)
