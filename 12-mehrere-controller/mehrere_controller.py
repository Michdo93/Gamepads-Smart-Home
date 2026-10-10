#!/usr/bin/env python3
"""
Kapitel 12 – Mehrere Controller gleichzeitig lesen (asyncio).

Jeder Controller aus config.yaml (Abschnitt gamepads) bekommt eine eigene Task.
Beim Xbox-360-Controller zeigt die Ring-LED danach die Nummer des Alias
(1. Regel = Spieler 1 ...), damit man sieht, welcher Controller welcher ist.

Aufruf:  python3 12-mehrere-controller/mehrere_controller.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.backends.evdev_backend import EvdevGamepad   # noqa: E402
from gamepadsmarthome.config import try_load_config               # noqa: E402
from gamepadsmarthome.devices import assign, list_gamepads         # noqa: E402
from gamepadsmarthome.feedback import set_led                      # noqa: E402


async def lesen(alias: str, pad: EvdevGamepad) -> None:
    async for ev in pad.async_events():
        if ev.kind != "axis" or abs(ev.value) > 0.5:
            print(ev)


async def main() -> int:
    cfg = try_load_config()
    if not cfg.gamepads:
        print("Bitte in config.yaml unter 'gamepads' Aliasse festlegen (Kapitel 12).")
        return 1
    zuordnung = assign(list_gamepads(), cfg.gamepads)
    tasks = []
    for nr, rule in enumerate(cfg.gamepads, start=1):
        info = zuordnung.get(rule["alias"])
        if info is None:
            print(f"{rule['alias']}: nicht gefunden")
            continue
        set_led(info.path, f"player_{min(nr, 4)}")
        print(f"{rule['alias']}: {info.path} ({info.name}) – Spieler {nr}")
        tasks.append(asyncio.create_task(lesen(rule["alias"], EvdevGamepad(info.path, pad=rule["alias"]))))
    if tasks:
        await asyncio.gather(*tasks)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
