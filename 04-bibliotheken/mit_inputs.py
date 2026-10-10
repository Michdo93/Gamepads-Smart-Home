#!/usr/bin/env python3
"""Kapitel 4 – Dieselbe Aufgabe mit drei Bibliotheken (3/3): inputs.

Aufruf:  python3 04-bibliotheken/mit_inputs.py
"""
from inputs import UnpluggedError, devices, get_gamepad

if not devices.gamepads:
    raise SystemExit("Kein Gamepad gefunden.")
print(devices.gamepads[0])

while True:
    try:
        events = get_gamepad()          # blockiert; liefert eine Liste von Ereignissen
    except UnpluggedError:
        raise SystemExit("Gamepad getrennt.")
    for e in events:
        if e.ev_type == "Key":
            print(f"Taste {e.code:<12} {'gedrückt' if e.state else 'losgelassen'}")
        elif e.ev_type == "Absolute":
            print(f"Achse {e.code:<12} {e.state:>7}")
