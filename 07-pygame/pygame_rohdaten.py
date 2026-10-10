#!/usr/bin/env python3
"""
Kapitel 7 – Was sieht pygame? Name, GUID, Anzahl der Tasten/Achsen/Hats und jede
Meldung mit ihrer NUMMER. Zeigt außerdem, ob SDL den Controller als
GameController kennt (dann gibt es eine feste Xbox-Belegung, Kapitel 8).

Aufruf:  python3 07-pygame/pygame_rohdaten.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends.pygame_backend import prepare_headless  # noqa: E402

prepare_headless()
import pygame                                 # noqa: E402
from pygame._sdl2 import controller           # noqa: E402

pygame.init()
controller.init()
print(f"pygame {pygame.version.ver}, SDL {'.'.join(map(str, pygame.get_sdl_version()))}")
if pygame.joystick.get_count() == 0:
    raise SystemExit("Kein Controller gefunden.")

for i in range(pygame.joystick.get_count()):
    j = pygame.joystick.Joystick(i)
    print(f"[{i}] {j.get_name()}")
    print(f"    GUID {j.get_guid()}  Tasten {j.get_numbuttons()}  Achsen {j.get_numaxes()}  "
          f"Hats {j.get_numhats()}  GameController: {'ja' if controller.is_controller(i) else 'nein'}")
    for a in range(j.get_numaxes()):
        print(f"    Achse {a}: Ruhewert {j.get_axis(a):+.2f}")
print("-" * 60)

while True:
    for e in pygame.event.get():
        if e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            print(f"[{e.instance_id}] Taste {e.button:>2} {'gedrückt' if e.type == pygame.JOYBUTTONDOWN else 'los'}")
        elif e.type == pygame.JOYAXISMOTION:
            print(f"[{e.instance_id}] Achse {e.axis:>2} {e.value:+.3f}")
        elif e.type == pygame.JOYHATMOTION:
            print(f"[{e.instance_id}] Hat   {e.hat:>2} {e.value}")
        elif e.type == pygame.JOYDEVICEADDED:
            print(f"Controller {e.device_index} angeschlossen")
        elif e.type == pygame.JOYDEVICEREMOVED:
            print(f"Controller {e.instance_id} getrennt")
    pygame.time.wait(10)
