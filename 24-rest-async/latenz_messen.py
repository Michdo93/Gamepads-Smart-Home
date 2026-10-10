#!/usr/bin/env python3
"""
Kapitel 24 – Warum die Ereignisschleife nie auf das Netzwerk warten darf.

Ein Stick erzeugt leicht 50 und mehr Ereignisse pro Sekunde. Wir spielen eine
Sekunde Stickbewegung (Farbkreis) ab und messen, wie spät jedes Ereignis
verarbeitet wird:

  blockierend    jedes Ereignis sendet sofort synchron (requests) – wie controller.py
  warteschlange  Ereignisse landen in einer Warteschlange; gesendet wird in eigenen
                 Tasks, beim Farbton nur der neueste Wert (Executor, Kapitel 23)

Mit künstlicher Antwortzeit wird der Unterschied deutlich:
  python3 00-virtuelle-geraete/mini_openhab.py --latenz 0.1      (zweites Terminal)

Aufruf:  python3 24-rest-async/latenz_messen.py --url http://127.0.0.1:8080
"""

import argparse
import asyncio
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamepadsmarthome.actions import Op                       # noqa: E402
from gamepadsmarthome.analog import stick_to_hue              # noqa: E402
from gamepadsmarthome.rest import OpenHABSender               # noqa: E402
from gamepadsmarthome.runtime import Executor                 # noqa: E402

ITEM = "iSmartHome_Hue_Lampen_Farbe"


def stickbahn(n: int = 50, dauer: float = 1.0):
    """n Ereignisse in 'dauer' Sekunden: Stick einmal im Kreis."""
    for i in range(n):
        w = 2 * math.pi * i / n
        yield i * dauer / n, math.sin(w), math.cos(w)


def bericht(name: str, verspaetung, gesendet: int, dauer: float) -> None:
    print(f"{name:<14} Verspätung Ø {statistics.mean(verspaetung) * 1000:7.0f} ms   "
          f"max {max(verspaetung) * 1000:7.0f} ms   gesendet {gesendet:>3}   Gesamtzeit {dauer:5.2f} s")


def blockierend(url: str, token) -> None:
    from openhab import Items, OpenHABClient
    items = Items(OpenHABClient(url=url, token=token))
    start, verspaetung, gesendet, last = time.monotonic(), [], 0, None
    for t, x, y in stickbahn():
        while time.monotonic() - start < t:          # Ereignis "kommt" zum Zeitpunkt t
            time.sleep(0.001)
        verspaetung.append(time.monotonic() - start - t)
        hue = stick_to_hue(x, y, 0.5, 5)
        if hue is not None and hue != last:
            last = hue
            items.sendCommand(ITEM, f"{hue},100,70")  # blockiert die Schleife
            gesendet += 1
    bericht("blockierend", verspaetung, gesendet, time.monotonic() - start)


async def warteschlange(url: str, token) -> None:
    async with OpenHABSender(url, token=token) as sender:
        ex = Executor(sender, min_interval=0.1).start()
        start, verspaetung, last = time.monotonic(), [], None
        for t, x, y in stickbahn():
            await asyncio.sleep(max(0.0, t - (time.monotonic() - start)))
            verspaetung.append(time.monotonic() - start - t)
            hue = stick_to_hue(x, y, 0.5, 5)
            if hue is not None and hue != last:
                last = hue
                ex.submit([Op("latest", ITEM, f"{hue},100,70")])   # kehrt sofort zurück
        await ex.drain()
        await ex.stop()
        bericht("warteschlange", verspaetung, len(ex.done), time.monotonic() - start)


def main() -> int:
    ap = argparse.ArgumentParser(description="Blockierend oder Warteschlange?")
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--token")
    args = ap.parse_args()
    blockierend(args.url, args.token)
    asyncio.run(warteschlange(args.url, args.token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
