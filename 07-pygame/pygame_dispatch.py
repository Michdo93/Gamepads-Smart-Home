#!/usr/bin/env python3
"""
Kapitel 7 – Der Xbox-360-Controller aus dem Repo xbox360controller, neu aufgebaut.

Statt einer langen if/elif-Kette je Taste steht die Zuordnung in einem Wörterbuch
(Dispatch-Tabelle). Neue Tasten oder andere Reaktionen ändern nur die Tabelle, nicht
die Schleife. Die Nummern kommen aus der Mapping-Datei – damit läuft dasselbe
Programm auch mit dem DualShock 4.

Aufruf:  python3 07-pygame/pygame_dispatch.py [--mapping xbox360_wireless]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepadsmarthome.backends.pygame_backend import PygameGamepad   # noqa: E402
from gamepadsmarthome.events import dpad_name                         # noqa: E402
from gamepadsmarthome.mapping import Mapping                          # noqa: E402

# Reaktionen: (Steuerelement, Zustand) -> Funktion
def ansage(text):
    return lambda ev: print(text)


AKTIONEN = {
    ("a", 1): ansage("A gedrückt – zum Beispiel: Licht an/aus"),
    ("b", 1): ansage("B gedrückt"),
    ("x", 1): ansage("X gedrückt"),
    ("y", 1): ansage("Y gedrückt"),
    ("lb", 1): ansage("LB: vorheriger Raum"),
    ("rb", 1): ansage("RB: nächster Raum"),
    ("start", 1): ansage("Start: Morgenroutine"),
}


def stick(ev):
    if abs(ev.value) > 0.5:
        richtung = {"lx": ("links", "rechts"), "ly": ("unten", "oben"),
                    "rx": ("links", "rechts"), "ry": ("unten", "oben")}[ev.control]
        print(f"Stick {ev.control[0]} nach {richtung[ev.value > 0]} ({ev.value:+.2f})")


def main() -> int:
    ap = argparse.ArgumentParser(description="pygame mit Dispatch-Tabelle")
    ap.add_argument("--mapping", help="Mapping-Datei (Standard: automatisch)")
    ap.add_argument("--index", type=int, default=0)
    args = ap.parse_args()
    pad = PygameGamepad(args.index, Mapping.load(args.mapping) if args.mapping else None)
    print(f"{pad.name} – Mapping {pad.mapping.source.stem}")
    for ev in pad.events():
        if ev.kind == "button":
            AKTIONEN.get((ev.control, ev.value), lambda e: None)(ev)
        elif ev.kind == "dpad":
            print(f"Steuerkreuz: {dpad_name(ev.value)}")
        elif ev.control in ("lt", "rt") and ev.value > 0.5:
            print(f"Trigger {ev.control.upper()} {ev.value:.2f}")
        elif ev.control in ("lx", "ly", "rx", "ry"):
            stick(ev)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
