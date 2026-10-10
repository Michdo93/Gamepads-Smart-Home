#!/usr/bin/env python3
"""
Kapitel 3 – Welche Eingabegeräte sieht Linux, und welche davon sind Gamepads?

Zeigt für jedes Gerät unter /dev/input: Name, USB-Kennung, phys, uniq,
Treiber und ob es als Gamepad erkannt wird. Für Gamepads außerdem die Mapping-Datei,
die die Begleitbibliothek automatisch wählen würde.

Aufruf:  python3 03-linux/geraete_auflisten.py [--alle]
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepadsmarthome.devices import is_gamepad          # noqa: E402
from gamepadsmarthome.mapping import find_mapping        # noqa: E402


def driver(path: str) -> str:
    """Name des Kerneltreibers – über sysfs, z. B. xpad oder playstation."""
    event = Path(path).name
    for up in ("device/device/driver", "device/device/device/driver"):
        link = Path("/sys/class/input") / event / up
        if link.exists():
            return Path(os.path.realpath(link)).name
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--alle", action="store_true", help="auch Tastaturen, Mäuse usw. zeigen")
    args = ap.parse_args()
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        print("python-evdev fehlt:  pip install evdev")
        return 1

    paths = list_devices()
    if not paths:
        print("Keine lesbaren Eingabegeräte. Ist der Benutzer in der Gruppe 'input'?")
        return 1
    for path in sorted(paths, key=lambda p: int(p.rsplit("event", 1)[1])):
        dev = InputDevice(path)
        pad = is_gamepad(dev.capabilities())
        if pad or args.alle:
            print(f"{path:<20} {'GAMEPAD' if pad else '':<8} {dev.name}")
            print(f"{'':<20} usb={dev.info.vendor:04x}:{dev.info.product:04x}  "
                  f"treiber={driver(path)}  phys={dev.phys or '-'}  uniq={dev.uniq or '-'}")
            if pad:
                m = find_mapping(dev.name, dev.info.vendor, dev.info.product)
                print(f"{'':<20} mapping={m.source.stem}  ({m.name})")
        dev.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
