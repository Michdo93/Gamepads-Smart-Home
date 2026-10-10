#!/usr/bin/env python3
"""
Kapitel 12 – Alle Gamepads mit ihren festen Merkmalen – und die Zuordnung zu Aliassen.

Aufruf:  python3 12-mehrere-controller/controller_liste.py [--config config/config.yaml]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.config import try_load_config         # noqa: E402
from gamepadsmarthome.devices import assign, list_gamepads   # noqa: E402

cfg = try_load_config(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--config" else None)
pads = list_gamepads()
if not pads:
    sys.exit("Kein Gamepad gefunden.")
for p in pads:
    print(f"{p.path:<20} {p.name}")
    print(f"{'':<20} usb={p.usb_id}  phys={p.phys or '-'}  uniq={p.uniq or '-'}")
    for link in p.by_id:
        print(f"{'':<20} by-id: {link}")
zuordnung = assign(pads, cfg.gamepads)
print("\nZuordnung laut config.yaml:" if cfg.gamepads else "\nKeine Regeln in config.yaml (Abschnitt gamepads).")
for alias, p in zuordnung.items():
    print(f"  {alias:<14} -> {p.path}  ({p.name}, {p.phys})")
for rule in cfg.gamepads:
    if rule["alias"] not in zuordnung:
        print(f"  {rule['alias']:<14} -> NICHT GEFUNDEN  {rule}")
