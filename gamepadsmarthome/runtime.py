"""
runtime.py – Logging, Kommandozeile und die asynchrone Hauptschleife für Ansatz B.

Executor        führt Operationen aus actions.Profile gegen openHAB aus:
                  command/toggle/carry  der Reihe nach über eine Warteschlange
                  latest          je Item nur der NEUESTE Wert, höchstens alle
                                  min_interval Sekunden ("latest wins")
run_controller  verbindet Ereignisquelle, Bedienlogik, Profil und Executor.

Die Ereignisschleife wartet nie auf das Netzwerk: Sie legt Befehle nur in eine
Warteschlange. Gesendet wird in eigenen Tasks – so bleibt der Controller auch dann
reaktionsschnell, wenn openHAB oder eine Hue-Bridge einmal langsam antwortet.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import AsyncIterator, Callable, Dict, List, Optional

from .actions import Op, Profile
from .events import GamepadEvent
from .logic import ControlLogic, Gesture

log = logging.getLogger("gamepadruntime")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")


def base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--config", help="Pfad zur config.yaml (Standard: config/config.yaml)")
    p.add_argument("-v", "--verbose", action="store_true", help="ausführliche Ausgabe")
    return p


class Executor:
    """Operationen ausführen. sender braucht send(item, value, force) und toggle(item)."""

    def __init__(self, sender, min_interval: float = 0.1,
                 feedback: Optional[Callable[[str, str], None]] = None):
        self.sender = sender
        self.min_interval = min_interval
        self.feedback = feedback
        self.queue: asyncio.Queue = asyncio.Queue()
        self.latest: Dict[str, str] = {}
        self._wake = asyncio.Event()
        self._tasks: List[asyncio.Task] = []
        self.done: List[Op] = []                      # Protokoll (für Tests und Ausgabe)

    def submit(self, ops: List[Op]) -> None:
        for op in ops:
            if op.kind == "latest":
                self.latest[op.item] = op.value       # älterer Wert wird überschrieben
                self._wake.set()
            elif op.kind == "feedback":
                if self.feedback:
                    self.feedback(op.item, op.value)
                self.done.append(op)
            else:
                self.queue.put_nowait(op)

    async def _commands(self) -> None:
        while True:
            op: Op = await self.queue.get()
            try:
                if op.kind == "toggle":
                    new = await self.sender.toggle(op.item)
                    log.info("%-40s -> %s (umgeschaltet)", op.item, new)
                elif op.kind == "carry":              # läuft das alte Gerät, zieht es mit um
                    if await self.sender.state(op.item) == "ON":
                        await self.sender.send(op.item, "OFF", force=True)
                        await self.sender.send(op.value, "ON", force=True)
                        log.info("%-40s -> OFF, %s -> ON", op.item, op.value)
                else:
                    await self.sender.send(op.item, op.value, force=True)
                    log.info("%-40s -> %s", op.item, op.value)
                self.done.append(op)
            except Exception as exc:
                log.error("Befehl %s fehlgeschlagen: %s", op, exc)
            finally:
                self.queue.task_done()

    async def _latest(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self.latest:
                item, value = self.latest.popitem()
                try:
                    await self.sender.send(item, value, force=True)
                    log.info("%-40s -> %s", item, value)
                    self.done.append(Op("latest", item, value))
                except Exception as exc:
                    log.error("Wert %s=%s fehlgeschlagen: %s", item, value, exc)
                await asyncio.sleep(self.min_interval)      # Gerät/Bridge schonen

    def start(self) -> "Executor":
        self._tasks = [asyncio.create_task(self._commands()), asyncio.create_task(self._latest())]
        return self

    async def drain(self, timeout: float = 2.0) -> None:
        """Warten, bis alles gesendet ist (für Tests und sauberes Beenden)."""
        try:
            await asyncio.wait_for(self.queue.join(), timeout)
        except asyncio.TimeoutError:
            log.warning("Nicht alle Befehle gesendet")
        end = time.monotonic() + timeout
        while self.latest and time.monotonic() < end:
            await asyncio.sleep(0.02)
        await asyncio.sleep(self.min_interval)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


async def run_controller(events: AsyncIterator[GamepadEvent], logic: ControlLogic,
                         profile: Profile, executor: Executor,
                         on_gesture: Optional[Callable[[Gesture], None]] = None,
                         tick: float = 0.02) -> None:
    """Hauptschleife: Ereignisse lesen, Gesten erkennen, Operationen ausführen."""

    def dispatch(gestures: List[Gesture]) -> None:
        for g in gestures:
            if on_gesture:
                on_gesture(g)
            executor.submit(profile.handle(g))

    async def ticker() -> None:
        while True:
            await asyncio.sleep(tick)
            dispatch(logic.tick(time.monotonic()))

    tick_task = asyncio.create_task(ticker())
    try:
        async for ev in events:
            dispatch(logic.feed(ev))
            executor.submit(profile.handle_analog(ev))
    finally:
        tick_task.cancel()
        await asyncio.gather(tick_task, return_exceptions=True)

