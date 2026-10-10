#!/usr/bin/env python3
"""
Kapitel 18 – Das MQTT-Gateway: Gamepad-Ereignisse nach Mosquitto, Rückkanal zum Controller.

Für jeden Controller aus config.yaml (Abschnitt gamepads) liest das Gateway die
Ereignisse, erkennt Gesten (Kapitel 10) und veröffentlicht beides unter
gamepad/<alias>/... (Topic-Schema in gamepadsmarthome/mqtt.py). openHAB entscheidet
über Regeln, was passiert (Kapitel 20).

Rückkanal: gamepad/<alias>/set/rumble und gamepad/<alias>/set/led steuern Vibration
und LEDs (Kapitel 21).

Ein Controller, der sich abschaltet oder getrennt wird, meldet sich als offline; das
Gateway wartet, bis er wieder da ist.

Aufruf:
  python3 18-mqtt-gateway/gamepad_mqtt_gateway.py
  python3 18-mqtt-gateway/gamepad_mqtt_gateway.py --dry-run --replay 08-mapping/aufnahmen/labor_rundgang.jsonl
    (ohne Controller und ohne Broker: Nachrichten nur ausgeben)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamepadsmarthome import feedback                                  # noqa: E402
from gamepadsmarthome.backends import replay                           # noqa: E402
from gamepadsmarthome.config import Config, try_load_config            # noqa: E402
from gamepadsmarthome.logic import ControlLogic                        # noqa: E402
from gamepadsmarthome.mqtt import GamepadMqtt, GatewayEncoder, Message  # noqa: E402
from gamepadsmarthome.runtime import setup_logging                     # noqa: E402

log = logging.getLogger("gateway")


class PrintSink:
    """Ersatz für GamepadMqtt bei --dry-run: Nachrichten nur ausgeben."""

    def __init__(self) -> None:
        self.sent: List[Message] = []

    def send(self, messages: List[Message]) -> None:
        for topic, payload, retain in messages:
            self.sent.append((topic, payload, retain))
            print(f"{topic:<36} {payload:<14} {'(retained)' if retain else ''}")

    def on(self, pattern, handler) -> None:
        pass


class PadWorker:
    """Ein Controller: Ereignisse lesen, Gesten erkennen, Nachrichten erzeugen."""

    def __init__(self, alias: str, cfg: Config, sink, rule: Optional[dict] = None,
                 replay_file: Optional[str] = None, speed: float = 1.0):
        mq = cfg.section("mqtt")
        self.alias, self.sink, self.rule = alias, sink, rule or {}
        self.replay_file, self.speed = replay_file, speed
        self.logic = ControlLogic.from_config(cfg.section("logic"), pad=alias)
        self.encoder = GatewayEncoder(alias, mq.get("base_topic", "gamepad"),
                                      float(mq.get("rate_hz", 10)), int(mq.get("step", 5)))
        self.mapping_dirs = [ROOT / d for d in cfg.get("mapping_dirs", [])]
        self.path: Optional[str] = None
        self.device = None
        self.rumble: Optional[feedback.Rumble] = None

    # -- Ereignisquelle --------------------------------------------------------------
    async def _events(self):
        if self.replay_file:
            async for ev in replay.async_play(replay.load(self.replay_file, self.alias), self.speed):
                yield ev
            return
        from gamepadsmarthome.backends.evdev_backend import EvdevGamepad
        from gamepadsmarthome.devices import assign, list_gamepads
        from gamepadsmarthome.mapping import find_mapping
        waiting_logged = False
        while True:
            pads = list_gamepads()
            info = assign(pads, [self.rule]).get(self.alias) if self.rule else (pads[0] if pads else None)
            if info is None:
                if not waiting_logged:
                    log.info("%s: warte auf Controller ...", self.alias)
                    waiting_logged = True
                await asyncio.sleep(2)
                continue
            waiting_logged = False
            mapping = find_mapping(info.name, info.vendor, info.product, self.mapping_dirs)
            pad = EvdevGamepad(info.path, mapping, pad=self.alias)
            self.path, self.device = info.path, pad.device
            self.rumble = feedback.Rumble(pad.device)
            log.info("%s: %s (%s, Mapping %s)", self.alias, info.name, info.path, mapping.source.stem)
            self.sink.send(self.encoder.status(True))
            self.report_battery()
            try:
                async for ev in pad.async_events():
                    yield ev
            except OSError as exc:
                log.warning("%s: Verbindung verloren (%s)", self.alias, exc)
            finally:
                self.path = self.device = self.rumble = None
                self.sink.send(self.encoder.status(False))
                try:
                    pad.close()
                except OSError:
                    pass

    async def run(self) -> None:
        if self.replay_file:
            self.sink.send(self.encoder.status(True))
        async for ev in self._events():
            msgs = self.encoder.event(ev)
            for g in self.logic.feed(ev):
                msgs += self.encoder.gesture(g)
            self.sink.send(msgs)
        if self.replay_file:                 # Aufzeichnung zu Ende: ausstehende Gesten senden
            await asyncio.sleep(1.0)

    def tick(self, now: float) -> None:
        msgs: List[Message] = []
        for g in self.logic.tick(now):
            msgs += self.encoder.gesture(g)
        msgs += self.encoder.flush(now)
        if msgs:
            self.sink.send(msgs)

    def report_battery(self) -> None:
        if self.path:
            b = feedback.battery(self.path)
            if b:
                self.sink.send(self.encoder.battery(b[0]))

    # -- Rückkanal --------------------------------------------------------------------
    def handle_set(self, what: str, payload: str) -> None:
        log.info("%s: Rückmeldung %s = %s", self.alias, what, payload)
        if what == "rumble":
            if self.rumble is None or not self.rumble.supported:
                return
            asyncio.get_event_loop().create_task(self._rumble(payload))
        elif what == "led" and self.path:
            value = int(payload) if payload.isdigit() else payload
            feedback.set_led(self.path, value)

    async def _rumble(self, payload: str) -> None:
        if payload in feedback.PATTERNS:
            steps = feedback.PATTERNS[payload]
        else:
            parts = [float(p) for p in payload.split(",")]
            steps = [(parts[0], parts[1], int(parts[2]))]
        for strong, weak, ms in steps:
            if (strong or weak) and self.rumble:
                self.rumble.play(strong, weak, ms)
            await asyncio.sleep(ms / 1000)


async def main_async(args) -> int:
    cfg = try_load_config(args.config)
    mq = cfg.section("mqtt")
    base = mq.get("base_topic", "gamepad")
    if args.dry_run:
        sink = PrintSink()
    else:
        if not mq:
            print("Abschnitt mqtt fehlt in config.yaml (Vorlage: config/config.example.yaml).")
            return 1
        sink = GamepadMqtt.from_config(mq).start()

    if args.replay:
        workers = [PadWorker(args.alias or "wohnzimmer", cfg, sink, None, args.replay, args.speed)]
    else:
        rules = cfg.gamepads or [{"alias": "pad0"}]
        workers = [PadWorker(r["alias"], cfg, sink, r if len(r) > 1 else None) for r in rules]
    by_alias: Dict[str, PadWorker] = {w.alias: w for w in workers}

    loop = asyncio.get_running_loop()

    def on_set(topic: str, payload: str) -> None:       # läuft im paho-Thread
        parts = topic.split("/")                        # gamepad/<alias>/set/<was>
        worker = by_alias.get(parts[1]) if len(parts) == 4 else None
        if worker:
            loop.call_soon_threadsafe(worker.handle_set, parts[3], payload)
    sink.on(f"{base}/+/set/+", on_set)

    async def ticker() -> None:
        last_battery = time.monotonic()
        while True:
            await asyncio.sleep(0.02)
            now = time.monotonic()
            for w in workers:
                w.tick(now)
            if now - last_battery > 60:
                last_battery = now
                for w in workers:
                    w.report_battery()

    tick_task = asyncio.create_task(ticker())
    try:
        await asyncio.gather(*(w.run() for w in workers))
    finally:
        tick_task.cancel()
        if not args.dry_run:
            sink.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Gamepad -> MQTT")
    ap.add_argument("--config")
    ap.add_argument("--dry-run", action="store_true", help="nicht senden, nur ausgeben")
    ap.add_argument("--replay", help="Aufzeichnung statt Controller")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--alias", help="Alias für --replay (Standard: wohnzimmer)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
