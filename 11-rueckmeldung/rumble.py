#!/usr/bin/env python3
"""
Kapitel 11 – Vibration (Rumble) über evdev: einzelner Stoß oder benanntes Muster.

Aufruf:
  python3 11-rueckmeldung/rumble.py --muster klingel
  python3 11-rueckmeldung/rumble.py --stark 1.0 --schwach 0.2 --ms 500
Rechte: Schreibzugriff auf /dev/input/eventN (Gruppe input genügt).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.devices import list_gamepads          # noqa: E402
from gamepadsmarthome.feedback import PATTERNS, Rumble      # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Gamepad vibrieren lassen")
    ap.add_argument("--path", help="/dev/input/eventN (Standard: erstes Gamepad)")
    ap.add_argument("--muster", choices=sorted(PATTERNS))
    ap.add_argument("--stark", type=float, default=0.6, help="großer Motor 0..1")
    ap.add_argument("--schwach", type=float, default=0.6, help="kleiner Motor 0..1")
    ap.add_argument("--ms", type=int, default=300)
    args = ap.parse_args()
    from evdev import InputDevice
    path = args.path or (list_gamepads() or [None])[0]
    if path is None:
        print("Kein Gamepad gefunden.")
        return 1
    dev = InputDevice(path if isinstance(path, str) else path.path)
    rumble = Rumble(dev)
    if not rumble.supported:
        print(f"{dev.name} unterstützt kein FF_RUMBLE.")
        return 1
    schritte = PATTERNS[args.muster] if args.muster else [(args.stark, args.schwach, args.ms)]
    for stark, schwach, ms in schritte:
        if stark or schwach:
            rumble.play(stark, schwach, ms)
        time.sleep(ms / 1000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
