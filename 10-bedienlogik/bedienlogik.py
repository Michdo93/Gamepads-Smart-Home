#!/usr/bin/env python3
"""
Kapitel 10 – Bedienlogik live: kurz, lang, doppelt, Wiederholung, Ebenen, Stick-Richtungen.

Aufruf:  python3 10-bedienlogik/bedienlogik.py [--modifier lb] [--alle] [--replay DATEI]
  --alle   auch press/release anzeigen (sonst nur short, long, double, repeat, Richtungen)
"""

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.config import try_load_config                 # noqa: E402
from gamepadsmarthome.logic import ControlLogic                     # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Bedienlogik anzeigen")
    ap.add_argument("--modifier", action="append", default=None, help="Ebenentaste, z. B. lb")
    ap.add_argument("--alle", action="store_true")
    add_source_args(ap)
    args = ap.parse_args()
    cfg = try_load_config(None)
    opts = cfg.section("logic")
    if args.modifier:
        opts["modifiers"] = args.modifier
    logic = ControlLogic.from_config(opts, pad=args.alias or "pad0")
    lock = threading.Lock()

    def show(gestures):
        for g in gestures:
            if args.alle or g.gesture not in ("press", "release"):
                print(f"{time.strftime('%H:%M:%S')}  {g}")

    def ticker():                   # long und repeat entstehen durch Zeit, nicht durch Ereignisse
        while True:
            time.sleep(0.02)
            with lock:
                show(logic.tick(time.monotonic()))

    threading.Thread(target=ticker, daemon=True).start()
    for ev in open_source(args, cfg).events():
        with lock:
            show(logic.feed(ev))
    time.sleep(1.0)                 # nach einer Aufzeichnung: ausstehende long/repeat zeigen
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
