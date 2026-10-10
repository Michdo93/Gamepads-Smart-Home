"""
backends – Eingabe von verschiedenen Quellen, Ausgabe immer als GamepadEvent.

  evdev_backend   Linux-Eingabegeräte über python-evdev (Kapitel 6)
  pygame_backend  SDL über pygame: Joystick-API oder GameController-API (Kapitel 7, 8)
  replay          Aufzeichnungen abspielen – zum Testen ohne Controller (Kapitel 8)

Die Übersetzer (EvdevTranslator, PygameTranslator, GameControllerTranslator) sind
reine Funktionen ohne Hardwarezugriff und deshalb leicht zu testen.
"""

from .base import DpadState, emit_changes  # noqa: F401
