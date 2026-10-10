#!/usr/bin/env python3
"""
Kapitel 6 – Rohdaten eines Gamepads mit python-evdev.

Zeigt zuerst, was das Gerät kann (Tasten, Achsen mit Wertebereich), dann jede
Meldung mit Typ, Code-Namen und Wert. EV_SYN-Meldungen trennen Pakete (--syn).

Aufruf:  python3 06-evdev/evdev_rohdaten.py [/dev/input/eventN] [--syn]
"""

import argparse
import sys

from evdev import InputDevice, ecodes, list_devices


def first_gamepad():
    for p in list_devices():
        if ecodes.BTN_SOUTH in InputDevice(p).capabilities().get(ecodes.EV_KEY, []):
            return p
    return None


def code_name(table, code) -> str:
    """ecodes liefert für manche Codes eine Liste (BTN_A und BTN_SOUTH ...)."""
    name = table.get(code, hex(code))
    return "/".join(name) if isinstance(name, list) else name


def main() -> int:
    ap = argparse.ArgumentParser(description="Rohdaten eines Gamepads (evdev)")
    ap.add_argument("path", nargs="?", help="/dev/input/eventN (Standard: erstes Gamepad)")
    ap.add_argument("--syn", action="store_true", help="auch EV_SYN anzeigen")
    args = ap.parse_args()
    path = args.path or first_gamepad()
    if not path:
        print("Kein Gamepad gefunden – ist der Benutzer in der Gruppe 'input'?")
        return 1

    dev = InputDevice(path)
    caps = dev.capabilities(absinfo=True)
    print(f"{dev.path}: {dev.name}  (usb {dev.info.vendor:04x}:{dev.info.product:04x})")
    print("Tasten:", ", ".join(code_name(ecodes.BTN, c) if c in ecodes.BTN else code_name(ecodes.KEY, c)
                               for c in caps.get(ecodes.EV_KEY, [])))
    print("Achsen:")
    for code, info in caps.get(ecodes.EV_ABS, []):
        print(f"  {code_name(ecodes.ABS, code):<11} {info.min:>7} .. {info.max:<7} "
              f"Ruhe {info.value:>6}  flat {info.flat}  fuzz {info.fuzz}")
    if ecodes.EV_FF in caps:
        print("Force Feedback:", ", ".join(code_name(ecodes.FF, c) for c in caps[ecodes.EV_FF]))
    print("-" * 60)

    for e in dev.read_loop():
        if e.type == ecodes.EV_SYN:
            if args.syn:
                print("  --- SYN ---")
            continue
        if e.type == ecodes.EV_KEY:
            table = ecodes.BTN if e.code in ecodes.BTN else ecodes.KEY
            print(f"{e.timestamp():.3f}  EV_KEY  {code_name(table, e.code):<28} {e.value}")
        elif e.type == ecodes.EV_ABS:
            print(f"{e.timestamp():.3f}  EV_ABS  {code_name(ecodes.ABS, e.code):<28} {e.value}")
        else:
            print(f"{e.timestamp():.3f}  typ {e.type}  code {e.code}  wert {e.value}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
