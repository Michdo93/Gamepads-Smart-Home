#!/usr/bin/env python3
"""
Kapitel 6 – Logische Ereignisse statt Rohdaten: EvdevGamepad aus der Begleitbibliothek.

Aus "EV_ABS ABS_Y -32768" wird "axis ly +1.00" (Stick oben), aus "EV_KEY 0x2c2 1"
beim Funkempfänger "dpad (0, 1)". Die Mapping-Datei wird automatisch gewählt.

Aufruf:  python3 06-evdev/evdev_gamepad.py [/dev/input/eventN] [--mapping xbox360_wireless]
                                           [--deadzone 0.15]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepadsmarthome.analog import deadzone_axial                 # noqa: E402
from gamepadsmarthome.backends.base import emit_changes             # noqa: E402
from gamepadsmarthome.backends.evdev_backend import EvdevGamepad    # noqa: E402
from gamepadsmarthome.devices import list_gamepads                  # noqa: E402
from gamepadsmarthome.events import GamepadEvent                    # noqa: E402
from gamepadsmarthome.mapping import Mapping                        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Logische Gamepad-Ereignisse (evdev)")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--mapping", help="Name oder Pfad einer Mapping-Datei")
    ap.add_argument("--deadzone", type=float, default=0.15)
    args = ap.parse_args()

    path = args.path
    if not path:
        pads = list_gamepads()
        if not pads:
            print("Kein Gamepad gefunden.")
            return 1
        path = pads[0].path
    pad = EvdevGamepad(path, Mapping.load(args.mapping) if args.mapping else None)
    print(f"{path}: {pad.name}  ->  Mapping {pad.mapping.source.stem}")

    last: dict = {}
    def filtered():
        for ev in pad.events():
            if ev.kind == "axis" and ev.control in ("lx", "ly", "rx", "ry"):
                ev = GamepadEvent(ev.kind, ev.control, round(deadzone_axial(ev.value, args.deadzone), 2),
                                  ev.pad, ev.t)
            yield ev
    for ev in emit_changes(filtered(), last, axis_tolerance=0.02):
        print(ev)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
