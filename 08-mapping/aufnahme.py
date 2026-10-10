#!/usr/bin/env python3
"""
Kapitel 8 – Gamepad-Ereignisse aufzeichnen (JSON-Zeilen), um sie später ohne
Controller abzuspielen: auf dem Entwicklungsrechner, in Tests, im Buch.

Aufruf:  python3 08-mapping/aufnahme.py aufnahmen/meine.jsonl [--backend pygame]
Beenden mit Strg+C.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends.replay import Recorder   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Gamepad-Ereignisse aufzeichnen")
    ap.add_argument("datei")
    ap.add_argument("--backend", choices=["evdev", "pygame"], default="evdev")
    args = ap.parse_args()
    if args.backend == "evdev":
        from gamepadsmarthome.backends.evdev_backend import EvdevGamepad
        from gamepadsmarthome.devices import list_gamepads
        pads = list_gamepads()
        if not pads:
            print("Kein Gamepad gefunden.")
            return 1
        pad = EvdevGamepad(pads[0].path)
    else:
        from gamepadsmarthome.backends.pygame_backend import PygameGamepad
        pad = PygameGamepad(0)
    print(f"Aufnahme von {pad.name} nach {args.datei} – Strg+C beendet")
    n = 0
    with open(args.datei, "w", encoding="utf-8") as fh:
        rec = Recorder(fh)
        try:
            for ev in pad.events():
                rec.write(ev)
                n += 1
        except KeyboardInterrupt:
            pass
    print(f"\n{n} Ereignisse gespeichert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
