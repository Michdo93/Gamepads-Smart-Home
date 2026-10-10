"""
codes.py – die evdev-Codes, die bei Gamepads vorkommen (aus linux/input-event-codes.h).

python-evdev bringt dieselben Konstanten in evdev.ecodes mit. Wir halten die wenigen
benötigten Werte hier selbst vor, damit Mapping-Dateien und Tests auch ohne
python-evdev (etwa unter Windows oder in einer CI) funktionieren.

Achtung: Der Kernel kennt für vier Tasten je ZWEI Namen mit demselben Wert:
  BTN_A == BTN_SOUTH (304)   BTN_B == BTN_EAST (305)
  BTN_X == BTN_NORTH (307)   BTN_Y == BTN_WEST (308)
Die Himmelsrichtungen beschreiben die Lage der Taste, die Buchstaben stammen aus
der Zeit vor dieser Festlegung. Welcher Wert für welche Taste kommt, entscheidet
der Treiber – deshalb messen wir es (Kapitel 8).
"""

from __future__ import annotations

from typing import Dict, Union

EV_SYN, EV_KEY, EV_ABS, EV_FF = 0x00, 0x01, 0x03, 0x15

CODES: Dict[str, int] = {
    # Tasten
    "BTN_SOUTH": 0x130, "BTN_A": 0x130,
    "BTN_EAST": 0x131, "BTN_B": 0x131,
    "BTN_C": 0x132,
    "BTN_NORTH": 0x133, "BTN_X": 0x133,
    "BTN_WEST": 0x134, "BTN_Y": 0x134,
    "BTN_Z": 0x135,
    "BTN_TL": 0x136, "BTN_TR": 0x137, "BTN_TL2": 0x138, "BTN_TR2": 0x139,
    "BTN_SELECT": 0x13a, "BTN_START": 0x13b, "BTN_MODE": 0x13c,
    "BTN_THUMBL": 0x13d, "BTN_THUMBR": 0x13e,
    "BTN_DPAD_UP": 0x220, "BTN_DPAD_DOWN": 0x221, "BTN_DPAD_LEFT": 0x222, "BTN_DPAD_RIGHT": 0x223,
    "BTN_TRIGGER_HAPPY1": 0x2c0, "BTN_TRIGGER_HAPPY2": 0x2c1,
    "BTN_TRIGGER_HAPPY3": 0x2c2, "BTN_TRIGGER_HAPPY4": 0x2c3,
    # Achsen
    "ABS_X": 0x00, "ABS_Y": 0x01, "ABS_Z": 0x02,
    "ABS_RX": 0x03, "ABS_RY": 0x04, "ABS_RZ": 0x05,
    "ABS_GAS": 0x09, "ABS_BRAKE": 0x0a,
    "ABS_HAT0X": 0x10, "ABS_HAT0Y": 0x11,
}

# Rückwärts: Wert -> bevorzugter Name (Himmelsrichtung vor Buchstabe)
_PREFERRED = ["BTN_SOUTH", "BTN_EAST", "BTN_NORTH", "BTN_WEST"]
NAMES: Dict[int, str] = {}
for _name, _value in CODES.items():
    if _value not in NAMES or _name in _PREFERRED:
        NAMES[_value] = _name


def code(value: Union[int, str]) -> int:
    """'BTN_SOUTH' -> 304, 'ABS_X' -> 0, 304 -> 304, '0x130' -> 304."""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text in CODES:
        return CODES[text]
    try:
        return int(text, 0)
    except ValueError:
        pass
    try:  # unbekannter Name – vielleicht kennt ihn python-evdev
        from evdev import ecodes  # type: ignore
        return int(getattr(ecodes, text))
    except Exception as exc:
        raise ValueError(f"Unbekannter evdev-Code: {value!r}") from exc


def name(value: int, kind: int = EV_KEY) -> str:
    """304 -> 'BTN_SOUTH'; unbekannte Werte als Hex-Zahl."""
    if kind == EV_ABS:
        for n, v in CODES.items():
            if n.startswith("ABS_") and v == value:
                return n
    elif value in NAMES and not NAMES[value].startswith("ABS_"):
        return NAMES[value]
    return hex(value)
