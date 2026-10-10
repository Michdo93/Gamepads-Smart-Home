"""
gamepadsmarthome – Begleitbibliothek zum Buch „Smart Home & Gamepads“.

Module:
  events     GamepadEvent: ein Ereignis mit logischem Namen (a, lb, lx, dpad ...)
  codes      evdev-Codes (BTN_SOUTH, ABS_X ...) ohne installiertes python-evdev
  mapping    Mapping-Dateien je Controller: Rohcode -> logischer Name
  analog     Normalisierung, Deadzone, Kennlinie, Hysterese, Farbkreis, Drossel
  logic      Bedienlogik: kurz/lang/doppelt, Halten mit Wiederholung, Ebenen, Ringe
  backends   Eingabe über evdev, pygame (Joystick/GameController) oder Aufzeichnung
  devices    Gamepads unter /dev/input finden und eindeutig benennen
  feedback   Rückmeldung: Rumble, LEDs, Akkustand (evdev + sysfs)
  config     config/config.yaml laden
  mqtt       Ansatz A: MQTT-Gateway (paho-mqtt)
  rest       Ansatz B: openHAB-REST (python-openhab-rest-client)
  actions    Bedienprofile (YAML): Ereignis -> openHAB-Befehl
  runtime    Logging und Kommandozeile

Nur backends.evdev_backend, devices und feedback brauchen Linux und python-evdev;
alles andere läuft auf jedem System – auch ohne angeschlossenen Controller.
"""

import os

__version__ = "1.0.0"


def rel(path) -> str:
    """Pfad relativ zum aktuellen Verzeichnis – für kurze Ausgaben im Terminal."""
    try:
        return os.path.relpath(path)
    except ValueError:
        return str(path)
