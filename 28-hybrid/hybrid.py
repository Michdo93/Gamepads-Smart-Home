#!/usr/bin/env python3
"""
Kapitel 28 – Hybrid: schnell direkt per REST, sichtbar über MQTT.

Ein Programm, zwei Wege:
  * Zeitkritisches (Farbkreis, Helligkeit, Lautstärke, Rollladen) setzt das Programm
    selbst über die REST-API – nach dem Bedienprofil (Ansatz B).
  * Jede Geste geht zusätzlich als Ereignis an MQTT (gamepad/<alias>/event).
    openHAB kann darauf mit Regeln reagieren (Ansatz A) – etwa protokollieren,
    Szenen auslösen oder Gesten verarbeiten, die im Profil nicht vorkommen.

Aufruf:
  python3 28-hybrid/hybrid.py [--profil ...] [--replay DATEI] [--mqtt-dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "18-mqtt-gateway"))

from gamepadsmarthome.actions import Profile                              # noqa: E402
from gamepadsmarthome.config import try_load_config                       # noqa: E402
from gamepadsmarthome.logic import ControlLogic                           # noqa: E402
from gamepadsmarthome.mqtt import GamepadMqtt, GatewayEncoder             # noqa: E402
from gamepadsmarthome.rest import OpenHABSender                           # noqa: E402
from gamepadsmarthome.runtime import Executor, run_controller, setup_logging   # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source          # noqa: E402
from gamepad_mqtt_gateway import PrintSink                                # noqa: E402


async def main_async(args) -> int:
    cfg = try_load_config(args.config)
    oh, mq = cfg.section("openhab"), cfg.section("mqtt")
    if args.url:
        oh["url"] = args.url
    alias = args.alias or "wohnzimmer"
    profile = Profile.load(ROOT / (args.profil or cfg.get("profile") or "26-labor-szenarien/profile/labor.yaml"))
    logic = ControlLogic.from_config(cfg.section("logic"), pad=alias)
    sink = PrintSink() if args.mqtt_dry_run else GamepadMqtt.from_config(mq).start()
    encoder = GatewayEncoder(alias, mq.get("base_topic", "gamepad"))
    source = open_source(args, cfg)

    def melden(g) -> None:                        # jede Geste zusätzlich an MQTT
        if g.gesture not in ("press", "release"):
            sink.send(encoder.gesture(g))

    async with OpenHABSender.from_config(oh) as sender:
        ex = Executor(sender, float(oh.get("min_interval", 0.1))).start()
        try:
            await run_controller(source.async_events(), logic, profile, ex, on_gesture=melden)
            await asyncio.sleep(1.0)
            await ex.drain()
        finally:
            await ex.stop()
            if not args.mqtt_dry_run:
                sink.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="REST und MQTT kombiniert")
    ap.add_argument("--config")
    ap.add_argument("--profil")
    ap.add_argument("--url")
    ap.add_argument("--mqtt-dry-run", action="store_true", help="MQTT-Nachrichten nur ausgeben")
    ap.add_argument("-v", "--verbose", action="store_true")
    add_source_args(ap)
    args = ap.parse_args()
    setup_logging(args.verbose)
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
