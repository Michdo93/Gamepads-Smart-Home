#!/usr/bin/env python3
"""
Kapitel 22 – Dasselbe asynchron: AsyncOpenHABClient und AsyncItems.

Zehn Befehle nacheinander (await) und gleichzeitig (asyncio.gather) im Vergleich.
Mit künstlicher Antwortzeit wird der Unterschied deutlich:
  python3 00-virtuelle-geraete/mini_openhab.py --latenz 0.2

Aufruf:  python3 22-rest-grundlagen/rest_async.py
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.config import try_load_config   # noqa: E402

from openhab import AsyncItems, AsyncOpenHABClient    # noqa: E402

LAMPEN = ["iKueche", "iBad", "iIoT", "iSmartHome", "iMultimedia"]     # Räume mit Hue-Lampen


async def main(url: str, token) -> None:
    async with AsyncOpenHABClient(url=url, token=token) as client:
        items = AsyncItems(client)
        befehle = [(f"{r}_Hue_Lampen_Helligkeit", "INCREASE") for r in LAMPEN]

        t0 = time.perf_counter()
        for item, wert in befehle:                 # nacheinander
            await items.sendCommand(item, wert)
        t1 = time.perf_counter()
        await asyncio.gather(*(items.sendCommand(i, w) for i, w in befehle))   # gleichzeitig
        t2 = time.perf_counter()

        print(f"{len(befehle)} Befehle nacheinander: {(t1 - t0) * 1000:6.0f} ms")
        print(f"{len(befehle)} Befehle gleichzeitig: {(t2 - t1) * 1000:6.0f} ms")
        for r in LAMPEN:
            print(f"  {r}_Hue_Lampen_Helligkeit = {await items.getItemState(f'{r}_Hue_Lampen_Helligkeit')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="REST asynchron")
    ap.add_argument("--url")
    args = ap.parse_args()
    oh = try_load_config().section("openhab")
    asyncio.run(main(args.url or oh.get("url", "http://127.0.0.1:8080"), oh.get("token")))
