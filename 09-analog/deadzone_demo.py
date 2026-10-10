#!/usr/bin/env python3
"""
Kapitel 9 – Deadzone und Kennlinie im Vergleich.

Ohne Controller: Tabelle für eine Reihe von Auslenkungen.
Mit Controller (--live): linker Stick roh, axial, radial und mit Kennlinie.

Aufruf:  python3 09-analog/deadzone_demo.py [--dz 0.15] [--live | --replay DATEI]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.analog import curve, deadzone_axial, deadzone_radial   # noqa: E402
from gamepadsmarthome.config import try_load_config                          # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source             # noqa: E402


def tabelle(dz: float) -> None:
    print(f"{'roh':>6} {'axial':>7} {'Kennlinie²':>11}")
    for v in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0):
        a = deadzone_axial(v, dz)
        print(f"{v:>6.2f} {a:>7.2f} {curve(a, 2):>11.2f}")
    print("\nRadial: Richtung bleibt erhalten (x, y) -> (x', y')")
    for x, y in ((0.1, 0.1), (0.12, 0.0), (0.5, 0.05), (0.7, 0.7)):
        rx, ry = deadzone_radial(x, y, dz)
        ax, ay = deadzone_axial(x, dz), deadzone_axial(y, dz)
        print(f"  ({x:.2f}, {y:.2f})  radial ({rx:+.2f}, {ry:+.2f})   axial ({ax:+.2f}, {ay:+.2f})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Deadzone und Kennlinie")
    ap.add_argument("--dz", type=float, default=0.15)
    ap.add_argument("--live", action="store_true", help="mit angeschlossenem Controller")
    add_source_args(ap)
    args = ap.parse_args()
    if not (args.live or args.replay):
        tabelle(args.dz)
        return 0
    xy = [0.0, 0.0]
    for ev in open_source(args, try_load_config()).events():
        if ev.control in ("lx", "ly"):
            xy[0 if ev.control == "lx" else 1] = ev.value
            rx, ry = deadzone_radial(xy[0], xy[1], args.dz)
            print(f"roh ({xy[0]:+.2f}, {xy[1]:+.2f})  axial ({deadzone_axial(xy[0], args.dz):+.2f}, "
                  f"{deadzone_axial(xy[1], args.dz):+.2f})  radial ({rx:+.2f}, {ry:+.2f})  "
                  f"Kennlinie ({curve(rx):+.2f}, {curve(ry):+.2f})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
