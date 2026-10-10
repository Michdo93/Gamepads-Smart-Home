#!/usr/bin/env python3
"""
Kapitel 11 – Akkustand des Controllers (sofern der Treiber ihn meldet).

hid-playstation (DualShock 4, DualSense) meldet Ladestand und Status über
power_supply. xpad meldet beim Xbox-360-Controller keinen Akkustand.

Aufruf:  python3 11-rueckmeldung/akku.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.devices import list_gamepads   # noqa: E402
from gamepadsmarthome.feedback import battery        # noqa: E402

pads = list_gamepads()
if not pads:
    sys.exit("Kein Gamepad gefunden.")
for p in pads:
    b = battery(p.path)
    print(f"{p.path:<20} {p.name:<40} " + (f"{b[0]:>3} %  {b[1]}" if b else "kein Akkustand"))
