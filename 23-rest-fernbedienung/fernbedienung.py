#!/usr/bin/env python3
"""
Kapitel 23 – Ansatz B: Der Controller als Fernbedienung über die REST-API.

Ereignisse lesen -> Bedienlogik (Kapitel 10) -> Bedienprofil (YAML) -> Executor.
Die Belegung steht vollständig im Profil; das Programm selbst kennt kein einziges Item.

Aufruf:
  python3 23-rest-fernbedienung/fernbedienung.py
  python3 23-rest-fernbedienung/fernbedienung.py --profil 23-rest-fernbedienung/profile/xbox360_original.yaml
  python3 23-rest-fernbedienung/fernbedienung.py --replay 08-mapping/aufnahmen/labor_rundgang.jsonl
    (ohne Controller; mit Mini-openHAB auch ohne openHAB)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamepadsmarthome import feedback                                   # noqa: E402
from gamepadsmarthome.actions import Profile                            # noqa: E402
from gamepadsmarthome.config import try_load_config                     # noqa: E402
from gamepadsmarthome.logic import ControlLogic                         # noqa: E402
from gamepadsmarthome.rest import OpenHABSender                         # noqa: E402
from gamepadsmarthome.runtime import Executor, run_controller, setup_logging   # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source        # noqa: E402

log = logging.getLogger("fernbedienung")


def make_feedback(source):
    """Rückmeldungen aus dem Profil (feedback: led/rumble) an den echten Controller."""
    path = source.path
    rumble = None
    if source.pad is not None and hasattr(source.pad, "device") and hasattr(source.pad.device, "capabilities"):
        rumble = feedback.Rumble(source.pad.device)

    def handler(kind: str, value: str) -> None:
        log.info("Rückmeldung %s = %s", kind, value)
        if kind == "led" and path:
            feedback.set_led(path, int(value) if value.isdigit() else value)
        elif kind == "rumble" and rumble is not None and rumble.supported:
            strong, weak, ms = feedback.PATTERNS.get(value, [(0.5, 0.5, 200)])[0]
            rumble.play(strong, weak, ms)
    return handler


async def main_async(args) -> int:
    cfg = try_load_config(args.config)
    oh = cfg.section("openhab")
    if args.url:
        oh["url"] = args.url
    if "url" not in oh:
        print("Abschnitt openhab fehlt in config.yaml (oder --url angeben).")
        return 1
    profile_path = Path(args.profil or cfg.get("profile") or ROOT / "26-labor-szenarien/profile/labor.yaml")
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = Profile.load(profile_path)
    logic = ControlLogic.from_config(cfg.section("logic"), pad=args.alias or "pad0")
    source = open_source(args, cfg)
    log.info("Quelle: %s – Profil: %s (%s)", source.name, profile.name, profile_path.name)

    async with OpenHABSender.from_config(oh) as sender:
        executor = Executor(sender, float(oh.get("min_interval", 0.1)), make_feedback(source)).start()
        try:
            await run_controller(source.async_events(), logic, profile, executor,
                                 on_gesture=lambda g: log.debug("Geste %s", g))
            await asyncio.sleep(1.0)              # nach einer Aufzeichnung: long/repeat abwarten
            await executor.drain()
        finally:
            await executor.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Gamepad als Fernbedienung (REST)")
    ap.add_argument("--config")
    ap.add_argument("--profil", help="Bedienprofil (YAML)")
    ap.add_argument("--url", help="openHAB-URL (überschreibt config.yaml)")
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
