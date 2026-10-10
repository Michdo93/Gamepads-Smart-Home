"""
feedback.py – der Controller antwortet: Vibration, Leuchten, Akkustand.

Vibration (Rumble) läuft über evdev (Force Feedback, EV_FF); LEDs und Akku über
sysfs-Dateien, die der Treiber anlegt:

  Xbox 360 (xpad)          /sys/class/leds/xpad<N>/brightness     Muster 0..15
  DualShock 4 / DualSense  <hid>/leds/<input>:rgb:indicator/multi_intensity  "r g b"
                           <hid>/leds/<input>:white:player-<n>/brightness   (nur DualSense)
  Akku (hid-playstation)   <hid>/power_supply/ps-controller-battery-<mac>/capacity

Schreiben in sysfs erfordert Rechte – eine udev-Regel aus Kapitel 3 erledigt das.
Der Parameter sysfs erlaubt Tests mit einem nachgebauten Verzeichnisbaum.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("gamepadfeedback")

# Muster der Ring-LED des Xbox-360-Controllers (Kernel-Dokumentation xpad.rst)
XPAD_LED = {
    "off": 0, "blink_all": 1,
    "flash_1": 2, "flash_2": 3, "flash_3": 4, "flash_4": 5,
    "player_1": 6, "player_2": 7, "player_3": 8, "player_4": 9,
    "rotate": 10, "blink": 11, "blink_slow": 12, "rotate_two": 13,
    "blink_all_slow": 14, "blink_once": 15,
}


# -- Vibration -------------------------------------------------------------------
class Rumble:
    """Vibration über evdev. strong = großer Motor (links), weak = kleiner (rechts)."""

    def __init__(self, device):
        from evdev import ecodes, ff
        self.dev, self.ecodes, self.ff = device, ecodes, ff
        self._effect_id: Optional[int] = None

    @property
    def supported(self) -> bool:
        return self.ecodes.FF_RUMBLE in self.dev.capabilities().get(self.ecodes.EV_FF, [])

    def play(self, strong: float = 0.6, weak: float = 0.6, ms: int = 300) -> None:
        ff = self.ff
        rumble = ff.Rumble(strong_magnitude=int(0xFFFF * strong), weak_magnitude=int(0xFFFF * weak))
        effect = ff.Effect(self.ecodes.FF_RUMBLE, -1, 0, ff.Trigger(0, 0), ff.Replay(int(ms), 0),
                           ff.EffectType(ff_rumble_effect=rumble))
        if self._effect_id is not None:
            self.dev.erase_effect(self._effect_id)
        self._effect_id = self.dev.upload_effect(effect)
        self.dev.write(self.ecodes.EV_FF, self._effect_id, 1)


PATTERNS = {                 # benannte Vibrationsmuster für Rückmeldungen
    "kurz": [(0.4, 0.4, 120)],
    "doppelt": [(0.5, 0.5, 120), (0, 0, 120), (0.5, 0.5, 120)],
    "lang": [(0.8, 0.8, 600)],
    "klingel": [(1.0, 0.3, 250), (0, 0, 150), (1.0, 0.3, 250), (0, 0, 150), (1.0, 0.3, 250)],
}


# -- LEDs und Akku über sysfs --------------------------------------------------------
def hid_dir(event_path: str, sysfs: str = "/sys") -> Optional[Path]:
    """/dev/input/event5 -> Geräteverzeichnis des Treibers (dort liegen leds/, power_supply/)."""
    event = Path(event_path).name
    dev = Path(sysfs) / "class" / "input" / event / "device"
    try:
        real = Path(os.path.realpath(dev))      # .../inputN
    except OSError:
        return None
    return real.parent if real.exists() else None


def find_leds(event_path: str, sysfs: str = "/sys") -> Dict[str, Path]:
    """Alle LEDs des Controllers: {'xpad0': Path, 'input5:rgb:indicator': Path, ...}."""
    base = hid_dir(event_path, sysfs)
    leds: Dict[str, Path] = {}
    if base is None:
        return leds
    for candidate in (base / "leds", base.parent / "leds"):
        if candidate.is_dir():
            for led in sorted(candidate.iterdir()):
                leds[led.name] = led
    return leds


def _write(path: Path, value: str) -> bool:
    try:
        path.write_text(value)
        return True
    except OSError as exc:
        log.warning("Schreiben nach %s fehlgeschlagen: %s (udev-Regel aus Kapitel 3?)", path, exc)
        return False


def set_xpad_led(led: Path, pattern) -> bool:
    """Ring-LED des Xbox-360-Controllers: Name aus XPAD_LED oder Zahl 0..15."""
    value = XPAD_LED.get(pattern, pattern) if isinstance(pattern, str) else int(pattern)
    return _write(led / "brightness", str(int(value)))


def set_rgb_led(led: Path, rgb: Tuple[int, int, int], brightness: int = 255) -> bool:
    """Lightbar von DualShock 4 / DualSense (multicolor-LED)."""
    ok = _write(led / "multi_intensity", " ".join(str(int(c)) for c in rgb))
    return _write(led / "brightness", str(int(brightness))) and ok


def set_led(event_path: str, value, sysfs: str = "/sys") -> List[str]:
    """
    Passende LED des Controllers setzen:
      value = "player_2" / 7         -> Ring-LED (xpad)
      value = (255, 0, 0) / "255,0,0" -> Lightbar (hid-playstation)
    Liefert die Namen der geschriebenen LEDs.
    """
    written = []
    rgb = None
    if isinstance(value, str) and value.count(",") == 2:
        rgb = tuple(int(v) for v in value.split(","))
    elif isinstance(value, tuple):
        rgb = value
    for name, led in find_leds(event_path, sysfs).items():
        if rgb is not None and (led / "multi_intensity").exists():
            if set_rgb_led(led, rgb):  # type: ignore[arg-type]
                written.append(name)
        elif rgb is None and name.startswith("xpad"):
            if set_xpad_led(led, value):
                written.append(name)
    return written


def battery(event_path: str, sysfs: str = "/sys") -> Optional[Tuple[int, str]]:
    """(Ladestand in %, Status) – oder None, wenn der Treiber keinen Akku meldet."""
    base = hid_dir(event_path, sysfs)
    if base is None:
        return None
    for candidate in (base / "power_supply", base.parent / "power_supply"):
        if candidate.is_dir():
            for ps in sorted(candidate.iterdir()):
                cap = ps / "capacity"
                if cap.exists():
                    status = (ps / "status").read_text().strip() if (ps / "status").exists() else ""
                    return int(cap.read_text().strip()), status
    return None
