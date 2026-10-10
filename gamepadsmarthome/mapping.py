"""
mapping.py – Mapping-Dateien: welcher Rohcode ist welche Taste?

Jeder Controller meldet seine Tasten und Achsen mit anderen Nummern – und dieselbe
Hardware je nach Bibliothek und Treiber wieder anders. Eine Mapping-Datei
(gamepadsmarthome/mappings/*.yaml) übersetzt die Rohcodes in logische Namen
(siehe events.py). Aufbau:

    name: "Xbox 360 Wireless Receiver"
    match:                       # woran wir den Controller erkennen
      names: ["Xbox 360 Wireless Receiver"]
      usb:   ["045e:0719"]
    evdev:
      buttons: {a: BTN_SOUTH, b: BTN_EAST, ...}
      axes:
        lx: {code: ABS_X}
        ly: {code: ABS_Y, invert: true}      # evdev: oben = negativ
        lt: {code: ABS_Z, trigger: true}     # 0..1
      dpad: {hat: [ABS_HAT0X, ABS_HAT0Y]}    # oder:
      # dpad: {buttons: {up: BTN_TRIGGER_HAPPY3, ...}}
    pygame:                      # Joystick-API (Indizes)
      buttons: {a: 0, b: 1, ...}
      axes: {lx: {index: 0}, ly: {index: 1, invert: true}, lt: {index: 2, trigger: true}}
      dpad: {hat: 0}

Eigene Mapping-Dateien erzeugt der Mapping-Finder aus Kapitel 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml

from . import codes as C

MAPPING_DIR = Path(__file__).resolve().parent / "mappings"


@dataclass
class AxisSpec:
    name: str
    invert: bool = False
    trigger: bool = False
    lo: Optional[float] = None      # überschreibt den Bereich des Treibers
    hi: Optional[float] = None


@dataclass
class Section:
    """Abbildung für EINE Schnittstelle (evdev oder pygame)."""
    buttons: Dict[int, str] = field(default_factory=dict)        # Code/Index -> Name
    axes: Dict[int, AxisSpec] = field(default_factory=dict)      # Code/Index -> Achse
    hat: Optional[Union[Tuple[int, int], int]] = None            # evdev (x, y) / pygame Index
    dpad_buttons: Dict[int, Tuple[int, int]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Optional[dict], evdev: bool) -> "Section":
        d = d or {}
        conv = C.code if evdev else int
        sec = cls()
        for name, raw in (d.get("buttons") or {}).items():
            sec.buttons[conv(raw)] = str(name)
        for name, spec in (d.get("axes") or {}).items():
            if not isinstance(spec, dict):
                spec = {"code" if evdev else "index": spec}
            key = conv(spec.get("code", spec.get("index")))
            sec.axes[key] = AxisSpec(str(name), bool(spec.get("invert", False)),
                                     bool(spec.get("trigger", False)),
                                     spec.get("lo"), spec.get("hi"))
        dpad = d.get("dpad") or {}
        if "hat" in dpad:
            hat = dpad["hat"]
            sec.hat = (conv(hat[0]), conv(hat[1])) if evdev else int(hat)
        directions = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
        for direction, raw in (dpad.get("buttons") or {}).items():
            sec.dpad_buttons[conv(raw)] = directions[direction]
        return sec

    def to_dict(self, evdev: bool) -> dict:
        fmt = (lambda c: C.name(c)) if evdev else (lambda i: i)
        fmt_abs = (lambda c: C.name(c, C.EV_ABS)) if evdev else (lambda i: i)
        key = "code" if evdev else "index"
        out: dict = {"buttons": {n: fmt(c) for c, n in self.buttons.items()}, "axes": {}}
        for c, a in self.axes.items():
            spec = {key: fmt_abs(c)}
            if a.invert:
                spec["invert"] = True
            if a.trigger:
                spec["trigger"] = True
            out["axes"][a.name] = spec
        names = {(0, 1): "up", (0, -1): "down", (-1, 0): "left", (1, 0): "right"}
        if self.hat is not None:
            out["dpad"] = {"hat": [fmt_abs(self.hat[0]), fmt_abs(self.hat[1])] if evdev else self.hat}
        elif self.dpad_buttons:
            out["dpad"] = {"buttons": {names[v]: fmt(c) for c, v in self.dpad_buttons.items()}}
        return out


@dataclass
class Mapping:
    name: str
    names: List[str] = field(default_factory=list)
    usb: List[str] = field(default_factory=list)
    evdev: Section = field(default_factory=Section)
    pygame: Section = field(default_factory=Section)
    source: Optional[Path] = None
    notes: str = ""

    # -- Laden und Speichern -----------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict, source: Optional[Path] = None) -> "Mapping":
        match = d.get("match") or {}
        return cls(name=str(d.get("name", source.stem if source else "unbenannt")),
                   names=[str(n) for n in match.get("names", [])],
                   usb=[str(u).lower() for u in match.get("usb", [])],
                   evdev=Section.from_dict(d.get("evdev"), evdev=True),
                   pygame=Section.from_dict(d.get("pygame"), evdev=False),
                   source=source, notes=str(d.get("notes", "")))

    @classmethod
    def load(cls, name_or_path: Union[str, Path]) -> "Mapping":
        p = Path(name_or_path)
        if not p.suffix:
            p = MAPPING_DIR / f"{name_or_path}.yaml"
        with open(p, encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {}, source=p)

    def to_dict(self) -> dict:
        d = {"name": self.name, "match": {"names": self.names, "usb": self.usb}}
        if self.notes:
            d["notes"] = self.notes
        if self.evdev.buttons or self.evdev.axes:
            d["evdev"] = self.evdev.to_dict(evdev=True)
        if self.pygame.buttons or self.pygame.axes:
            d["pygame"] = self.pygame.to_dict(evdev=False)
        return d

    def save(self, path: Union[str, Path]) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.to_dict(), fh, allow_unicode=True, sort_keys=False)
        return p

    # -- Erkennen ------------------------------------------------------------------
    def matches(self, device_name: str = "", vendor: int = 0, product: int = 0) -> bool:
        if vendor and f"{vendor:04x}:{product:04x}" in self.usb:
            return True
        return any(n.lower() in device_name.lower() for n in self.names)


def available() -> List[Mapping]:
    """Alle mitgelieferten Mapping-Dateien; 'standard' zuletzt (Rückfallebene)."""
    maps = [Mapping.load(p) for p in sorted(MAPPING_DIR.glob("*.yaml"))]
    return sorted(maps, key=lambda m: m.source.stem == "standard")


def find_mapping(device_name: str = "", vendor: int = 0, product: int = 0,
                 extra_dirs: Optional[List[Path]] = None) -> Mapping:
    """Passende Mapping-Datei suchen – eigene Dateien (extra_dirs) haben Vorrang."""
    candidates: List[Mapping] = []
    for d in extra_dirs or []:
        candidates += [Mapping.load(p) for p in sorted(Path(d).glob("*.yaml"))]
    candidates += available()
    for m in candidates:                       # 1. eindeutig: USB-Kennung
        if vendor and m.matches("", vendor, product):
            return m
    for m in candidates:                       # 2. Gerätename
        if m.matches(device_name):
            return m
    return Mapping.load("standard")
