#!/usr/bin/env python3
"""
Kapitel 8 – Die GameController-API von SDL: feste Xbox-Belegung ohne Mapping-Datei.

Zeigt, ob SDL den Controller kennt, die Zuordnungszeile aus SDLs Datenbank
(gamecontrollerdb) und danach logische Ereignisse. Unbekannte Controller lassen
sich mit einer eigenen Zeile nachrüsten (Umgebungsvariable SDL_GAMECONTROLLERCONFIG).

Aufruf:  python3 08-mapping/gamecontroller.py [--index 0]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends.pygame_backend import PygameGamepad   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SDL GameController-API")
    ap.add_argument("--index", type=int, default=0)
    args = ap.parse_args()
    try:
        pad = PygameGamepad(args.index, gamecontroller=True)
    except RuntimeError as exc:
        print(exc)
        return 1
    print(f"{pad.name}\nSDL-Zuordnung: {pad.device.get_mapping()}\n")
    for ev in pad.events():
        print(ev)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
