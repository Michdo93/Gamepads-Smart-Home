#!/usr/bin/env python3
"""
Kapitel 8 – Eine Aufzeichnung abspielen und die Ereignisse ausgeben.

Aufruf:  python3 08-mapping/wiedergabe.py 08-mapping/aufnahmen/labor_rundgang.jsonl [--speed 2]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends import replay   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Aufzeichnung abspielen")
    ap.add_argument("datei")
    ap.add_argument("--speed", type=float, default=1.0, help="Abspielgeschwindigkeit")
    args = ap.parse_args()
    for ev in replay.play(replay.load(args.datei), args.speed):
        print(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
