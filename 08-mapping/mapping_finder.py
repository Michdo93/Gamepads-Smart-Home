#!/usr/bin/env python3
"""
Kapitel 8 – Der Mapping-Finder: Tasten nacheinander drücken, Mapping-Datei erhalten.

Das Programm fordert Taste für Taste und Achse für Achse dazu auf, das jeweilige
Steuerelement zu betätigen, und merkt sich, welcher Rohcode sich dabei meldet.
Ergebnis ist eine Mapping-Datei unter config/mappings/, die die Begleitbibliothek
künftig automatisch verwendet (sie hat Vorrang vor den mitgelieferten).

Aufruf:
  python3 08-mapping/mapping_finder.py                    # evdev, erstes Gamepad
  python3 08-mapping/mapping_finder.py --backend pygame   # pygame-Joystick-API
  python3 08-mapping/mapping_finder.py --name mein_pad --path /dev/input/event7

Eine Taste, die der Controller nicht hat (etwa guide), mit Strg+C überspringen.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamepadsmarthome.mapping import AxisSpec, Mapping, Section   # noqa: E402

# (Name, Art, Aufforderung)
STEPS: List[Tuple[str, str, str]] = [
    ("a", "button", "Taste A (unten; PlayStation: Kreuz)"),
    ("b", "button", "Taste B (rechts; Kreis)"),
    ("x", "button", "Taste X (links; Quadrat)"),
    ("y", "button", "Taste Y (oben; Dreieck)"),
    ("lb", "button", "linke Schultertaste LB / L1"),
    ("rb", "button", "rechte Schultertaste RB / R1"),
    ("back", "button", "Back / Share / Create"),
    ("start", "button", "Start / Options"),
    ("guide", "button", "Guide- bzw. PS-Taste"),
    ("ls", "button", "linken Stick hineindrücken"),
    ("rs", "button", "rechten Stick hineindrücken"),
    ("lx", "axis", "linken Stick ganz nach RECHTS"),
    ("ly", "axis", "linken Stick ganz nach OBEN"),
    ("rx", "axis", "rechten Stick ganz nach RECHTS"),
    ("ry", "axis", "rechten Stick ganz nach OBEN"),
    ("lt", "trigger", "linken Trigger LT / L2 ganz durchdrücken"),
    ("rt", "trigger", "rechten Trigger RT / R2 ganz durchdrücken"),
    ("up", "dpad", "Steuerkreuz OBEN"),
    ("down", "dpad", "Steuerkreuz UNTEN"),
    ("left", "dpad", "Steuerkreuz LINKS"),
    ("right", "dpad", "Steuerkreuz RECHTS"),
]


@dataclass
class Found:
    kind: str           # key | abs | hat
    ident: object       # evdev-Code bzw. pygame-Index; bei hat: (Hat, 'x'|'y')
    sign: int = 1


class Finder:
    """
    Erkennt aus Rohmeldungen, welches Steuerelement gerade betätigt wurde.
    Meldungen: ("key", id, gedrückt) | ("abs", id, wert) | ("hat", (hat, achse), wert)
    rest/ranges: Ruhewert und (min, max) je Achse.
    """

    def __init__(self, rest: Dict[object, float], ranges: Dict[object, Tuple[float, float]],
                 threshold: float = 0.6):
        self.rest, self.ranges, self.threshold = rest, ranges, threshold
        self.used: set = set()

    def feed(self, kind: str, sample: Tuple[str, object, float]) -> Optional[Found]:
        typ, ident, value = sample
        if ident in self.used and typ != "hat":
            return None
        if kind in ("button", "dpad") and typ == "key" and value:
            return self._take(Found("key", ident))
        if kind == "dpad" and typ == "hat" and value:      # Hat: x und y je eine Achse
            return Found("hat", ident, 1 if value > 0 else -1)
        if typ == "abs" and kind in ("axis", "trigger"):
            lo, hi = self.ranges.get(ident, (-1.0, 1.0))
            rest = self.rest.get(ident, (lo + hi) / 2)
            span = hi - lo
            if span <= 2:                    # Hat als Achse gemeldet – kein Stick
                return None
            delta = (value - rest) / span
            if kind == "axis" and abs(delta) >= self.threshold / 2:
                return self._take(Found("abs", ident, 1 if delta > 0 else -1))
            if kind == "trigger" and delta >= self.threshold:
                return self._take(Found("abs", ident, 1))
        return None

    def _take(self, found: Found) -> Found:
        self.used.add(found.ident)
        return found


def build_section(results: Dict[str, Found], evdev: bool) -> Section:
    sec = Section()
    directions = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
    hat: Dict[str, object] = {}
    for name, f in results.items():
        if name in directions:
            if f.kind == "key":
                sec.dpad_buttons[f.ident] = directions[name]            # type: ignore[index]
            elif f.kind == "hat":
                hat["y" if name in ("up", "down") else "x"] = f.ident
        elif f.kind == "key":
            sec.buttons[f.ident] = name                                 # type: ignore[index]
        elif f.kind == "abs":
            trigger = name in ("lt", "rt")
            # Ziel: rechts und oben positiv. Wurde der Rohwert dabei kleiner -> invertieren.
            sec.axes[f.ident] = AxisSpec(name, invert=(not trigger and f.sign < 0), trigger=trigger)  # type: ignore[index]
    if "x" in hat and "y" in hat:
        if evdev:
            sec.hat = (hat["x"], hat["y"])                              # type: ignore[assignment]
        else:
            sec.hat = hat["x"][0]                                       # type: ignore[index]
    return sec


# -- Rohmeldungen von evdev bzw. pygame ---------------------------------------------------
def evdev_source(path: Optional[str]):
    from evdev import InputDevice, ecodes
    from gamepadsmarthome.devices import list_gamepads
    if not path:
        pads = list_gamepads()
        if not pads:
            raise SystemExit("Kein Gamepad gefunden.")
        path = pads[0].path
    dev = InputDevice(path)
    rest, ranges = {}, {}
    for code, ai in dev.capabilities(absinfo=True).get(ecodes.EV_ABS, []):
        rest[code], ranges[code] = ai.value, (ai.min, ai.max)

    def samples():
        for e in dev.read_loop():
            if e.type == ecodes.EV_KEY and e.value in (0, 1):
                yield ("key", e.code, e.value)
            elif e.type == ecodes.EV_ABS:
                if 0x10 <= e.code <= 0x17:              # ABS_HAT0X .. ABS_HAT3Y
                    yield ("hat", e.code, -e.value if e.code % 2 else e.value)  # Y: oben = +1
                else:
                    yield ("abs", e.code, e.value)
    return dev.name, dev.info.vendor, dev.info.product, rest, ranges, samples()


def pygame_source(index: int):
    from gamepadsmarthome.backends.pygame_backend import prepare_headless
    prepare_headless()
    import pygame
    pygame.init()
    if pygame.joystick.get_count() <= index:
        raise SystemExit("Kein Controller gefunden.")
    j = pygame.joystick.Joystick(index)
    pygame.event.pump()
    rest = {a: j.get_axis(a) for a in range(j.get_numaxes())}
    ranges = {a: (-1.0, 1.0) for a in rest}
    # Trigger ruhen bei -1: Bereich bleibt -1..1, Ruhewert -1 -> Erkennung über delta
    def samples():
        while True:
            for e in pygame.event.get():
                if e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                    yield ("key", e.button, int(e.type == pygame.JOYBUTTONDOWN))
                elif e.type == pygame.JOYAXISMOTION:
                    yield ("abs", e.axis, e.value)
                elif e.type == pygame.JOYHATMOTION:
                    yield ("hat", (e.hat, "x"), e.value[0])
                    yield ("hat", (e.hat, "y"), e.value[1])
            pygame.time.wait(5)
    return j.get_name(), 0, 0, rest, ranges, samples()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "gamepad"


def main() -> int:
    ap = argparse.ArgumentParser(description="Mapping-Datei durch Tastendrücken erzeugen")
    ap.add_argument("--backend", choices=["evdev", "pygame"], default="evdev")
    ap.add_argument("--path", help="evdev: /dev/input/eventN")
    ap.add_argument("--index", type=int, default=0, help="pygame: Nummer des Controllers")
    ap.add_argument("--name", help="Dateiname (Standard: aus dem Gerätenamen)")
    ap.add_argument("--out", default=str(ROOT / "config" / "mappings"))
    args = ap.parse_args()

    evdev = args.backend == "evdev"
    name, vendor, product, rest, ranges, samples = (evdev_source(args.path) if evdev
                                                    else pygame_source(args.index))
    print(f"Gerät: {name}\nJeweils das genannte Element betätigen und wieder loslassen. "
          f"Strg+C überspringt ein Element.\n")
    finder = Finder(rest, ranges)
    results: Dict[str, Found] = {}
    for control, kind, prompt in STEPS:
        print(f"  {prompt:<45}", end="", flush=True)
        try:
            for s in samples:
                found = finder.feed(kind, s)
                if found:
                    results[control] = found
                    print(f"-> {found.kind} {found.ident}" + (" (invertiert)" if found.sign < 0 and kind == "axis" else ""))
                    break
        except KeyboardInterrupt:
            print("-> übersprungen")
        # Loslassen erzeugt nur "zurück in Ruhe"-Meldungen – die ignoriert der Finder.

    m = Mapping(name=name, names=[name], usb=[f"{vendor:04x}:{product:04x}"] if vendor else [],
                notes=f"Erzeugt mit mapping_finder.py ({args.backend})")
    sec = build_section(results, evdev)
    if evdev:
        m.evdev = sec
    else:
        m.pygame = sec
    target = Path(args.out) / f"{args.name or slug(name)}.yaml"
    if target.exists():                      # vorhandene Datei um den anderen Abschnitt ergänzen
        old = Mapping.load(target)
        if evdev:
            m.pygame = old.pygame
        else:
            m.evdev = old.evdev
    print(f"\nGespeichert: {m.save(target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
