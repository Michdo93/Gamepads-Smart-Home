#!/usr/bin/env python3
"""Kapitel 4 – Dieselbe Aufgabe mit drei Bibliotheken (1/3): python-evdev.

Gibt jede Taste und jede Achsbewegung des ersten Gamepads aus.
Aufruf:  python3 04-bibliotheken/mit_evdev.py [/dev/input/eventN]
"""
import sys

from evdev import InputDevice, categorize, ecodes, list_devices

path = sys.argv[1] if len(sys.argv) > 1 else None
if path is None:                       # erstes Gerät mit Gamepad-Tasten suchen
    for p in list_devices():
        if ecodes.BTN_SOUTH in InputDevice(p).capabilities().get(ecodes.EV_KEY, []):
            path = p
            break
if path is None:
    sys.exit("Kein Gamepad gefunden.")

dev = InputDevice(path)
print(f"{dev.path}: {dev.name}")
for event in dev.read_loop():          # blockiert, bis etwas passiert
    if event.type == ecodes.EV_KEY:
        print(categorize(event))       # z. B. "key event at ..., 304 (['BTN_A', 'BTN_GAMEPAD', 'BTN_SOUTH']), down"
    elif event.type == ecodes.EV_ABS:
        print(f"Achse {ecodes.ABS[event.code]:<10} {event.value:>7}")
