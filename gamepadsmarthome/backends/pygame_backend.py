"""
pygame_backend.py – Gamepads über pygame (SDL 2) lesen.

pygame bietet zwei Schnittstellen:

  Joystick-API        pygame.joystick – Tasten und Achsen nur als Nummern.
                      Welche Nummer welche Taste ist, hängt von Controller, Treiber
                      und SDL-Version ab -> Mapping-Datei (Abschnitt "pygame").
  GameController-API  pygame._sdl2.controller – SDL ordnet bekannte Controller über
                      seine Datenbank (gamecontrollerdb) einer festen Xbox-Belegung zu.
                      Keine Mapping-Datei nötig, aber nur für Controller, die SDL kennt.

Ohne Bildschirm (Raspberry Pi als Dienst) setzt prepare_headless() die nötigen
Umgebungsvariablen VOR pygame.init().
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

from ..analog import clamp
from ..events import GamepadEvent
from ..mapping import Mapping
from .base import DpadState


def prepare_headless() -> None:
    """pygame ohne Fenster betreiben und Ereignisse auch ohne Fokus empfangen."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


class PygameTranslator:
    """Ereignisse der Joystick-API (JOYBUTTONDOWN, JOYAXISMOTION, JOYHATMOTION)."""

    def __init__(self, mapping: Mapping, pad: str = "pad0", instance_id: Optional[int] = None):
        import pygame
        self.pg = pygame
        self.map = mapping.pygame
        self.pad = pad
        self.instance_id = instance_id
        self.dpad = DpadState()

    def translate(self, event, t: Optional[float] = None) -> List[GamepadEvent]:
        pg, t = self.pg, (time.monotonic() if t is None else t)
        if self.instance_id is not None and getattr(event, "instance_id", self.instance_id) != self.instance_id:
            return []
        out: List[GamepadEvent] = []
        if event.type in (pg.JOYBUTTONDOWN, pg.JOYBUTTONUP):
            pressed = event.type == pg.JOYBUTTONDOWN
            if event.button in self.map.buttons:
                out.append(GamepadEvent("button", self.map.buttons[event.button], int(pressed), self.pad, t))
            elif event.button in self.map.dpad_buttons:
                new = self.dpad.set_button(self.map.dpad_buttons[event.button], pressed)
                if new is not None:
                    out.append(GamepadEvent("dpad", "dpad", new, self.pad, t))
        elif event.type == pg.JOYHATMOTION and event.hat == self.map.hat:
            x, y = event.value                         # pygame: oben = +1
            out.append(GamepadEvent("dpad", "dpad", (int(x), int(y)), self.pad, t))
        elif event.type == pg.JOYAXISMOTION and event.axis in self.map.axes:
            spec = self.map.axes[event.axis]
            v = float(event.value)                     # SDL: -1.0 .. 1.0
            if spec.trigger:
                lo = -1.0 if spec.lo is None else spec.lo   # Ruhewert der Trigger ist -1
                hi = 1.0 if spec.hi is None else spec.hi
                v = clamp((v - lo) / (hi - lo), 0.0, 1.0)
            elif spec.invert:
                v = -v
            out.append(GamepadEvent("axis", spec.name, round(v, 4), self.pad, t))
        return out


class GameControllerTranslator:
    """Ereignisse der GameController-API (CONTROLLERBUTTONDOWN, CONTROLLERAXISMOTION)."""

    def __init__(self, pad: str = "pad0", instance_id: Optional[int] = None):
        import pygame as pg
        self.pg = pg
        self.pad = pad
        self.instance_id = instance_id
        self.dpad = DpadState()
        self.buttons = {
            pg.CONTROLLER_BUTTON_A: "a", pg.CONTROLLER_BUTTON_B: "b",
            pg.CONTROLLER_BUTTON_X: "x", pg.CONTROLLER_BUTTON_Y: "y",
            pg.CONTROLLER_BUTTON_LEFTSHOULDER: "lb", pg.CONTROLLER_BUTTON_RIGHTSHOULDER: "rb",
            pg.CONTROLLER_BUTTON_BACK: "back", pg.CONTROLLER_BUTTON_START: "start",
            pg.CONTROLLER_BUTTON_GUIDE: "guide",
            pg.CONTROLLER_BUTTON_LEFTSTICK: "ls", pg.CONTROLLER_BUTTON_RIGHTSTICK: "rs",
        }
        self.dpad_buttons = {
            pg.CONTROLLER_BUTTON_DPAD_UP: (0, 1), pg.CONTROLLER_BUTTON_DPAD_DOWN: (0, -1),
            pg.CONTROLLER_BUTTON_DPAD_LEFT: (-1, 0), pg.CONTROLLER_BUTTON_DPAD_RIGHT: (1, 0),
        }
        # Achsen: Sticks -32768..32767 (unten/rechts positiv), Trigger 0..32767
        self.axes = {
            pg.CONTROLLER_AXIS_LEFTX: ("lx", False), pg.CONTROLLER_AXIS_LEFTY: ("ly", True),
            pg.CONTROLLER_AXIS_RIGHTX: ("rx", False), pg.CONTROLLER_AXIS_RIGHTY: ("ry", True),
            pg.CONTROLLER_AXIS_TRIGGERLEFT: ("lt", False), pg.CONTROLLER_AXIS_TRIGGERRIGHT: ("rt", False),
        }

    def translate(self, event, t: Optional[float] = None) -> List[GamepadEvent]:
        pg, t = self.pg, (time.monotonic() if t is None else t)
        if self.instance_id is not None and getattr(event, "instance_id", self.instance_id) != self.instance_id:
            return []
        out: List[GamepadEvent] = []
        if event.type in (pg.CONTROLLERBUTTONDOWN, pg.CONTROLLERBUTTONUP):
            pressed = event.type == pg.CONTROLLERBUTTONDOWN
            if event.button in self.buttons:
                out.append(GamepadEvent("button", self.buttons[event.button], int(pressed), self.pad, t))
            elif event.button in self.dpad_buttons:
                new = self.dpad.set_button(self.dpad_buttons[event.button], pressed)
                if new is not None:
                    out.append(GamepadEvent("dpad", "dpad", new, self.pad, t))
        elif event.type == pg.CONTROLLERAXISMOTION and event.axis in self.axes:
            name, invert = self.axes[event.axis]
            if name in ("lt", "rt"):
                v = clamp(event.value / 32767.0, 0.0, 1.0)
            else:
                v = clamp(event.value / 32767.0)
                v = -v if invert else v
            out.append(GamepadEvent("axis", name, round(v, 4), self.pad, t))
        return out


class PygameGamepad:
    """
    Ein Gamepad über pygame öffnen (Joystick- oder GameController-API).

        prepare_headless()
        pad = PygameGamepad(0, mapping=Mapping.load("xbox360_wireless"))
        for ev in pad.events():
            print(ev)
    """

    def __init__(self, index: int = 0, mapping: Optional[Mapping] = None, pad: str = "pad0",
                 gamecontroller: bool = False, headless: bool = True):
        if headless:
            prepare_headless()
        import pygame
        pygame.init()
        pygame.joystick.init()
        self.pg = pygame
        if pygame.joystick.get_count() <= index:
            raise RuntimeError("Kein Controller gefunden (pygame.joystick.get_count() == "
                               f"{pygame.joystick.get_count()})")
        if gamecontroller:
            from pygame._sdl2 import controller
            controller.init()
            if not controller.is_controller(index):
                raise RuntimeError("SDL kennt diesen Controller nicht – Joystick-API mit Mapping-Datei verwenden")
            self.device = controller.Controller(index)
            joy = self.device.as_joystick()
            self.name = self.device.name
            self.mapping = None                    # feste Belegung durch SDL
            self.translator = GameControllerTranslator(pad, joy.get_instance_id())
        else:
            from ..mapping import find_mapping
            self.device = pygame.joystick.Joystick(index)
            self.device.init()
            self.name = self.device.get_name()
            self.mapping = mapping or find_mapping(self.name)
            self.translator = PygameTranslator(self.mapping, pad, self.device.get_instance_id())

    def rumble(self, strong: float = 0.6, weak: float = 0.6, ms: int = 300) -> bool:
        """Vibration über SDL (pygame 2): True, wenn der Controller sie unterstützt."""
        return bool(self.device.rumble(strong, weak, ms))

    def poll(self) -> List[GamepadEvent]:
        out: List[GamepadEvent] = []
        for event in self.pg.event.get():
            out += self.translator.translate(event)
        return out

    def events(self, wait_ms: int = 10) -> Iterator[GamepadEvent]:
        while True:
            yield from self.poll()
            self.pg.time.wait(wait_ms)            # CPU entlasten
