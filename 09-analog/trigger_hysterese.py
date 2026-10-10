#!/usr/bin/env python3
"""
Kapitel 9 – Trigger als Taste: mit und ohne Hysterese.

Ohne Hysterese (eine Schwelle 0.5) "flattert" der Zustand, wenn der Trigger um die
Schwelle zittert. Mit Hysterese (an ab 0.6, aus unter 0.4) gibt es genau einen
Druck. Ohne Controller wird ein zitternder Verlauf simuliert.

Aufruf:  python3 09-analog/trigger_hysterese.py [--live | --replay DATEI]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.analog import TriggerSwitch             # noqa: E402
from gamepadsmarthome.config import try_load_config           # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source   # noqa: E402

VERLAUF = [0.0, 0.3, 0.48, 0.52, 0.49, 0.55, 0.62, 0.58, 0.51, 0.47, 0.52, 0.45, 0.38, 0.1, 0.0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Trigger mit Hysterese")
    ap.add_argument("--live", action="store_true")
    add_source_args(ap)
    args = ap.parse_args()
    hyst = TriggerSwitch(0.6, 0.4)
    einfach = False
    werte = (ev.value for ev in open_source(args, try_load_config()).events() if ev.control == "rt") \
        if (args.live or args.replay) else iter(VERLAUF)
    n_einfach = n_hyst = 0
    for v in werte:
        neu = v >= 0.5
        if neu != einfach:
            einfach = neu
            n_einfach += neu
        h = hyst.update(v)
        n_hyst += h is True
        print(f"RT {v:4.2f}   Schwelle 0.5: {'AN ' if einfach else 'aus'}   "
              f"Hysterese: {'AN ' if hyst.pressed else 'aus'}{'  <- gedrückt' if h else ''}")
    print(f"\nDrücke erkannt – Schwelle: {n_einfach}, Hysterese: {n_hyst}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
