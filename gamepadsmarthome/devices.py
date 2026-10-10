"""
devices.py – Gamepads unter /dev/input finden und eindeutig benennen.

Die Nummer in /dev/input/eventN vergibt der Kernel in der Reihenfolge, in der Geräte
erscheinen – nach einem Neustart kann aus event5 ein event7 werden. Für eine feste
Zuordnung (Controller "wohnzimmer" -> Raum Multimedia) taugen andere Merkmale:

  uniq   eindeutige Kennung, bei Bluetooth die MAC-Adresse (bei USB oft leer)
  phys   physischer Anschluss, z. B. usb-0000:01:00.0-1.2/input0
         Beim Xbox-360-Funkempfänger unterscheidet die Endung (input0, input2,
         input4, input6) die vier Funkplätze – also die Spielernummer.
  by-id  symbolischer Link unter /dev/input/by-id/, aus Hersteller und Seriennummer

Mit assign() ordnen wir gefundene Geräte über Regeln aus config.yaml einem Alias zu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import codes as C


@dataclass
class PadInfo:
    path: str
    name: str
    phys: str = ""
    uniq: str = ""
    vendor: int = 0
    product: int = 0
    by_id: List[str] = field(default_factory=list)

    @property
    def usb_id(self) -> str:
        return f"{self.vendor:04x}:{self.product:04x}"

    @property
    def stable_id(self) -> str:
        """Bestes verfügbares festes Merkmal."""
        return self.uniq or (self.by_id[0] if self.by_id else "") or self.phys or self.path


def is_gamepad(capabilities: Dict[int, Iterable]) -> bool:
    """Gamepad = hat Gamepad-Tasten (ab BTN_SOUTH) UND mindestens eine X-Achse."""
    keys = set(capabilities.get(C.EV_KEY, []))
    absolute = {a[0] if isinstance(a, tuple) else a for a in capabilities.get(C.EV_ABS, [])}
    has_buttons = any(0x130 <= k <= 0x13e for k in keys)
    return has_buttons and C.CODES["ABS_X"] in absolute


def _by_id_links(directory: str = "/dev/input/by-id") -> Dict[str, List[str]]:
    links: Dict[str, List[str]] = {}
    d = Path(directory)
    if d.is_dir():
        for link in sorted(d.iterdir()):
            if "event" in link.name:
                links.setdefault(os.path.realpath(link), []).append(str(link))
    return links


def list_gamepads() -> List[PadInfo]:
    """Alle angeschlossenen Gamepads (benötigt python-evdev und Leserechte)."""
    from evdev import InputDevice, list_devices

    links = _by_id_links()
    pads = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except OSError:
            continue
        try:
            if is_gamepad(dev.capabilities()):
                pads.append(PadInfo(path, dev.name, dev.phys or "", dev.uniq or "",
                                    dev.info.vendor, dev.info.product,
                                    links.get(os.path.realpath(path), [])))
        finally:
            dev.close()
    return sorted(pads, key=lambda p: p.phys or p.path)


def assign(pads: Iterable[PadInfo], rules: Iterable[dict]) -> Dict[str, PadInfo]:
    """
    Regeln aus config.yaml (Abschnitt gamepads) auf gefundene Geräte anwenden:

        gamepads:
          - {alias: wohnzimmer, phys: "input0", name: "Xbox 360 Wireless"}
          - {alias: labor,      uniq: "a4:ae:12:34:56:78"}

    Jedes Feld ist ein Teilstring; alle angegebenen Felder müssen passen.
    Liefert {alias: PadInfo}. Jedes Gerät wird höchstens einem Alias zugeordnet.
    """
    result: Dict[str, PadInfo] = {}
    remaining = list(pads)
    for rule in rules:
        alias = str(rule["alias"])
        for pad in remaining:
            ok = True
            for key in ("name", "phys", "uniq", "usb", "path"):
                if key in rule:
                    have = pad.usb_id if key == "usb" else getattr(pad, key)
                    if str(rule[key]).lower() not in have.lower():
                        ok = False
            if ok:
                result[alias] = pad
                remaining.remove(pad)
                break
    return result


def find_pad(alias: Optional[str], rules: Iterable[dict]) -> Optional[PadInfo]:
    """Gerät zu einem Alias – ohne Alias einfach das erste gefundene Gamepad."""
    pads = list_gamepads()
    if not alias:
        return pads[0] if pads else None
    return assign(pads, rules).get(alias)
