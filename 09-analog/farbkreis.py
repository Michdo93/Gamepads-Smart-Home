#!/usr/bin/env python3
"""
Kapitel 9 – Der rechte Stick als Farbkreis.

Die Richtung des Sticks wird zum Farbton (0° = oben = Rot, im Uhrzeigersinn über
Gelb, Grün, Cyan, Blau, Magenta). Der Terminal zeigt die Farbe als Balken an
(24-Bit-Farben). Losgelassen bleibt die zuletzt gewählte Farbe stehen.

Aufruf:  python3 09-analog/farbkreis.py [--step 5] [--dz 0.5] [--replay DATEI]
"""

import argparse
import colorsys
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.analog import stick_to_hue          # noqa: E402
from gamepadsmarthome.config import try_load_config       # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source   # noqa: E402


def balken(hue: int) -> str:
    r, g, b = (int(c * 255) for c in colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0))
    return f"\x1b[48;2;{r};{g};{b}m{' ' * 20}\x1b[0m"


def main() -> int:
    ap = argparse.ArgumentParser(description="Stick als Farbkreis")
    ap.add_argument("--step", type=int, default=5, help="Raster in Grad")
    ap.add_argument("--dz", type=float, default=0.5, help="Mindestauslenkung")
    add_source_args(ap)
    args = ap.parse_args()
    xy, last = [0.0, 0.0], None
    for ev in open_source(args, try_load_config()).events():
        if ev.control not in ("rx", "ry"):
            continue
        xy[0 if ev.control == "rx" else 1] = ev.value
        hue = stick_to_hue(xy[0], xy[1], args.dz, args.step)
        if hue is not None and hue != last:
            last = hue
            print(f"Farbton {hue:>3}°  {balken(hue)}  openHAB: {hue},100,70")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
