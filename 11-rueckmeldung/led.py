#!/usr/bin/env python3
"""
Kapitel 11 – LEDs des Controllers setzen.

  Xbox 360:      --muster player_1 .. player_4 | rotate | blink_all | off | 0..15
  DS4/DualSense: --rgb 255,0,0

Aufruf:  python3 11-rueckmeldung/led.py --muster player_2
         python3 11-rueckmeldung/led.py --rgb 0,80,255
         python3 11-rueckmeldung/led.py --liste
Rechte: udev-Regel aus 03-linux/99-gamepads.rules.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.devices import list_gamepads           # noqa: E402
from gamepadsmarthome.feedback import XPAD_LED, find_leds, set_led   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Controller-LEDs setzen")
    ap.add_argument("--path")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--muster", help="Xbox-360-Muster: " + ", ".join(XPAD_LED))
    g.add_argument("--rgb", help="r,g,b für die Lightbar")
    g.add_argument("--liste", action="store_true", help="LEDs des Controllers anzeigen")
    args = ap.parse_args()
    pads = list_gamepads()
    path = args.path or (pads[0].path if pads else None)
    if path is None:
        print("Kein Gamepad gefunden.")
        return 1
    if args.liste:
        for name, led in find_leds(path).items():
            print(f"{name:<32} {led}")
        return 0
    value = args.rgb if args.rgb else (int(args.muster) if args.muster.isdigit() else args.muster)
    written = set_led(path, value)
    print("Gesetzt: " + (", ".join(written) if written else "keine passende LED gefunden"))
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
