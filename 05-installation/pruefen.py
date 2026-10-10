#!/usr/bin/env python3
"""
Kapitel 5 – Ist alles bereit? Prüft Python, Bibliotheken, Rechte und Kerneltreiber.

Aufruf:  python3 05-installation/pruefen.py
"""

import grp
import importlib
import os
import platform
import sys
from pathlib import Path

OK, FEHLT = "ok   ", "FEHLT"


def check(label: str, ok: bool, hint: str = "") -> bool:
    print(f"[{OK if ok else FEHLT}] {label}" + ("" if ok or not hint else f"  ->  {hint}"))
    return ok


def main() -> int:
    alles = True
    alles &= check(f"Python {platform.python_version()} (mind. 3.9)", sys.version_info >= (3, 9))
    for mod, hint in [("yaml", "pip install pyyaml"), ("evdev", "pip install evdev"),
                      ("pygame", "pip install pygame"), ("paho.mqtt", "pip install paho-mqtt"),
                      ("openhab", "pip install -r requirements.txt")]:
        try:
            importlib.import_module(mod)
            alles &= check(f"Modul {mod}", True)
        except ImportError:
            alles &= check(f"Modul {mod}", False, hint)

    try:
        gruppen = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    except KeyError:
        gruppen = set()
    alles &= check("Benutzer in Gruppe 'input'", "input" in gruppen or os.geteuid() == 0,
                   "sudo usermod -aG input $USER  (danach neu anmelden)")

    events = sorted(Path("/dev/input").glob("event*"))
    lesbar = [p for p in events if os.access(p, os.R_OK)]
    alles &= check(f"/dev/input: {len(lesbar)} von {len(events)} Geräten lesbar", bool(lesbar))

    module = {m: Path(f"/sys/module/{m}").exists() for m in ("xpad", "hid_playstation", "hid_sony", "uinput")}
    for m, geladen in module.items():
        print(f"[{'ok   ' if geladen else 'info '}] Kernelmodul {m} {'geladen' if geladen else 'nicht geladen'}")

    print("\nAlles bereit." if alles else "\nBitte die markierten Punkte beheben.")
    return 0 if alles else 1


if __name__ == "__main__":
    sys.exit(main())
