#!/usr/bin/env python3
"""
Kapitel 24 – Rückkanal ohne MQTT: openHAB-Zustände über Server-Sent Events beobachten
und am Controller melden (Vibration, LED).

  iSmartHome_Klingel -> ON      Vibrationsmuster "klingel"
  iSmartHome_Alarm   -> ON/OFF  lange Vibration und blinkende LEDs / LEDs normal

Aufruf:  python3 24-rest-async/rueckkanal_sse.py [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamepadsmarthome import feedback                         # noqa: E402
from gamepadsmarthome.config import try_load_config           # noqa: E402
from gamepadsmarthome.rest import OpenHABSender               # noqa: E402
from gamepadsmarthome.runtime import setup_logging            # noqa: E402

log = logging.getLogger("rueckkanal")


class Controller:
    """Vibration und LEDs des ersten Gamepads – oder nur Ausgabe (--dry-run)."""

    def __init__(self, dry_run: bool):
        self.path, self.rumble = None, None
        if not dry_run:
            from evdev import InputDevice
            from gamepadsmarthome.devices import list_gamepads
            pads = list_gamepads()
            if pads:
                self.path = pads[0].path
                self.rumble = feedback.Rumble(InputDevice(self.path))

    async def muster(self, name: str) -> None:
        log.info("Vibration: %s", name)
        for strong, weak, ms in feedback.PATTERNS[name]:
            if self.rumble and (strong or weak):
                self.rumble.play(strong, weak, ms)
            await asyncio.sleep(ms / 1000)

    def led(self, value) -> None:
        log.info("LED: %s", value)
        if self.path:
            feedback.set_led(self.path, value)


async def main_async(args) -> int:
    oh = try_load_config(args.config).section("openhab")
    url = args.url or oh.get("url", "http://127.0.0.1:8080")
    pad = Controller(args.dry_run)
    async with OpenHABSender(url, token=oh.get("token")) as sender:
        log.info("Beobachte Klingel und Alarm über %s/rest/events", url)
        async for item, state in sender.watch_states(["iSmartHome_Klingel", "iSmartHome_Alarm"]):
            if item == "iSmartHome_Klingel" and state == "ON":
                await pad.muster("klingel")
            elif item == "iSmartHome_Alarm":
                if state == "ON":
                    pad.led("blink_all_slow")
                    await pad.muster("lang")
                else:
                    pad.led("player_1")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Rückkanal über SSE")
    ap.add_argument("--config")
    ap.add_argument("--url")
    ap.add_argument("--dry-run", action="store_true", help="ohne Controller, nur Ausgabe")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
