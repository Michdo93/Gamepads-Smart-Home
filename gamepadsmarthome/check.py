"""
check.py – Passt ein Bedienprofil zu den Items? (Kapitel 25)

Jeder Item-Typ in openHAB nimmt nur bestimmte Befehle an. Ein INCREASE an einen
Switch oder ein UP an einen Dimmer verwirft openHAB mit einer Warnung im Log – das
merkt man erst, wenn man am Controller steht und nichts passiert. check_profile()
findet solche Fehler vorher: Es setzt alle Kombinationen der Auswahllisten ein
und prüft jedes Ziel-Item auf Existenz und passenden Befehl.
"""

from __future__ import annotations

import itertools
import re
from typing import Dict, Iterable, List, Tuple

from .actions import Profile

NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
HSB = re.compile(r"^\d{1,3},\d{1,3},\d{1,3}$")
PERCENT = lambda v: bool(NUMBER.match(v)) and 0 <= float(v) <= 100   # noqa: E731

# Item-Typ -> Prüffunktion für einen Befehl
ACCEPTS = {
    "Switch":        lambda v: v in ("ON", "OFF"),
    "Dimmer":        lambda v: v in ("ON", "OFF", "INCREASE", "DECREASE") or PERCENT(v),
    "Color":         lambda v: v in ("ON", "OFF", "INCREASE", "DECREASE") or PERCENT(v) or bool(HSB.match(v)),
    "Rollershutter": lambda v: v in ("UP", "DOWN", "STOP", "MOVE") or PERCENT(v),
    "Player":        lambda v: v in ("PLAY", "PAUSE", "NEXT", "PREVIOUS", "REWIND", "FASTFORWARD"),
    "Number":        lambda v: bool(NUMBER.match(v)),
    "String":        lambda v: True,
    "Contact":       lambda v: False,               # Contacts nehmen keine Befehle an
    "DateTime":      lambda v: True,
}

# Steuerelement -> passende Item-Typen und typische Befehle (Tabelle in Kapitel 25)
EMPFEHLUNG = [
    ("Taste kurz",            "Switch, Szene (String)",       "Umschalten (Zustand lesen, Gegenteil senden)"),
    ("Taste lang",            "Gruppe, Routine",              "selten Gebrauchtes, Folgenreiches"),
    ("Steuerkreuz (halten)",  "Dimmer, Lautstärke",           "INCREASE / DECREASE mit Wiederholung"),
    ("Steuerkreuz",           "Player, Fernseher (String)",   "NEXT / PREVIOUS, KEY_UP ..."),
    ("Stick-Richtung",        "Rollershutter, PTZ (String)",  "UP / DOWN beim Auslenken, STOP beim Loslassen"),
    ("Stick-Winkel",          "Color",                        "Farbton H,S,B"),
    ("Trigger analog",        "Dimmer",                       "absolute Helligkeit 0..100"),
    ("Trigger als Taste",     "Auswahl (Ring)",               "Sender, Raum, Szene weiterschalten"),
    ("Schultertasten",        "Auswahl (Ring)",               "Raum oder Modus wechseln"),
]


def _combinations(profile: Profile) -> Iterable[None]:
    """Alle Kombinationen der Ringe (und Modi) durchlaufen; liefert nichts, setzt nur den Zustand."""
    names = list(profile.rings)
    modes = list(profile.modes) or [None]
    for mode in modes:
        if mode:
            profile.mode.select(mode)  # type: ignore[union-attr]
        for combo in itertools.product(*(profile.rings[n].entries for n in names)):
            for n, v in zip(names, combo):
                profile.rings[n].select(v)
            yield None


def _specs(profile: Profile) -> List[dict]:
    tables = [profile.actions] + [m["actions"] for m in profile.modes.values()]
    out: List[dict] = []
    for table in tables:
        for specs in table.values():
            for s in specs:
                out.append(s)
                for key in ("before", "after"):
                    extra = s.get(key)
                    if extra:
                        out += extra if isinstance(extra, list) else [extra]
    return out


def targets(profile: Profile) -> List[Tuple[str, str, str]]:
    """Alle (Item, Befehl, Art) – Art: command | toggle | carry | hue | dimmer."""
    found = set()
    specs = _specs(profile)
    analogs = [profile.analog] + [m["analog"] for m in profile.modes.values()]
    for _ in _combinations(profile):
        for s in specs:
            if "command" in s:
                found.add((profile.fill(s["command"]), profile.fill(s.get("value", "")), "command"))
            elif "toggle" in s:
                found.add((profile.fill(s["toggle"]), "ON", "toggle"))
            elif "carry" in s:
                found.add((profile.fill(s["carry"]), "ON", "carry"))
        for a in analogs:
            for spec in a.values():
                if "hue" in spec:
                    found.add((profile.fill(spec["hue"]), "0,100,70", "hue"))
                if "dimmer" in spec:
                    found.add((profile.fill(spec["dimmer"]), "50", "dimmer"))
    return sorted(found)


def check_profile(profile: Profile, items: Dict[str, dict]) -> List[str]:
    """Fehlerliste (leer = alles in Ordnung). items: Name -> {'type': ..., 'groupType': ...}."""
    errors = []
    for item, value, kind in targets(profile):
        if "{" in item:
            errors.append(f"{item}: Platzhalter nicht aufgelöst")
            continue
        if item not in items:
            errors.append(f"{item}: Item existiert nicht ({kind})")
            continue
        typ = items[item]["type"].split(":")[0]
        if typ == "Group":
            typ = (items[item].get("groupType") or "String").split(":")[0]
        check = ACCEPTS.get(typ)
        if check and not check(value):
            errors.append(f"{item}: {typ} nimmt '{value}' nicht an ({kind})")
    return errors
