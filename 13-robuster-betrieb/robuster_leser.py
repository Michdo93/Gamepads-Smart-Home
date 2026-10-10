#!/usr/bin/env python3
"""
Kapitel 13 – Ein Leser, der Trennen und Wiederverbinden übersteht.

Der Xbox-360-Controller schaltet sich nach einigen Minuten ohne Eingabe ab, ein
Akku wird leer, ein Kabel wird gezogen, USB/IP verliert kurz die Verbindung – das
Eingabegerät verschwindet, und read() wirft OSError. Statt abzustürzen wartet das
Programm, bis das Gerät (per Alias aus config.yaml) wieder da ist.

Aufruf:  python3 13-robuster-betrieb/robuster_leser.py [--alias wohnzimmer]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends.evdev_backend import EvdevGamepad   # noqa: E402
from gamepadsmarthome.config import try_load_config               # noqa: E402
from gamepadsmarthome.devices import find_pad                      # noqa: E402
from gamepadsmarthome.runtime import setup_logging                 # noqa: E402

log = logging.getLogger("robust")


async def warte_auf_controller(alias, rules, intervall: float = 2.0):
    gemeldet = False
    while True:
        info = find_pad(alias, rules)
        if info:
            return info
        if not gemeldet:
            log.info("Warte auf Controller %s ...", alias or "(erstes Gamepad)")
            gemeldet = True
        await asyncio.sleep(intervall)


async def main() -> int:
    ap = argparse.ArgumentParser(description="Robuster Gamepad-Leser")
    ap.add_argument("--alias")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)
    cfg = try_load_config()
    while True:
        info = await warte_auf_controller(args.alias, cfg.gamepads)
        pad = EvdevGamepad(info.path, pad=args.alias or "pad0")
        log.info("Verbunden: %s (%s)", info.name, info.path)
        try:
            async for ev in pad.async_events():
                log.debug("%s", ev)
                if ev.kind == "button" and ev.value:
                    log.info("Taste %s", ev.control)
        except OSError as exc:              # Gerät verschwunden (errno 19: No such device)
            log.warning("Verbindung verloren: %s", exc)
        finally:
            try:
                pad.close()
            except OSError:
                pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
