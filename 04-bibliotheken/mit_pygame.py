#!/usr/bin/env python3
"""Kapitel 4 – Dieselbe Aufgabe mit drei Bibliotheken (2/3): pygame (SDL 2).

Aufruf:  python3 04-bibliotheken/mit_pygame.py
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"                    # kein Fenster nötig
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"   # Ereignisse auch ohne Fokus

import pygame  # noqa: E402

pygame.init()
if pygame.joystick.get_count() == 0:
    raise SystemExit("Kein Controller gefunden.")
joy = pygame.joystick.Joystick(0)
print(f"{joy.get_name()}: {joy.get_numbuttons()} Tasten, {joy.get_numaxes()} Achsen, "
      f"{joy.get_numhats()} Hats")

while True:
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            print(f"Taste {event.button} gedrückt")
        elif event.type == pygame.JOYBUTTONUP:
            print(f"Taste {event.button} losgelassen")
        elif event.type == pygame.JOYAXISMOTION:
            print(f"Achse {event.axis} {event.value:+.2f}")
        elif event.type == pygame.JOYHATMOTION:
            print(f"Hat {event.hat} {event.value}")
    pygame.time.wait(10)                                   # CPU entlasten
