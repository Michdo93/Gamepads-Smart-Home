#!/usr/bin/env python3
"""
Kapitel 25 – Bedienprofil prüfen: Gibt es alle Items, und passt jeder Befehl zum Item-Typ?

Die Items kommen wahlweise aus openHAB (REST) oder offline aus Items-Dateien.

Aufruf:
  python3 25-item-typen/profil_pruefen.py 26-labor-szenarien/profile/labor.yaml
  python3 25-item-typen/profil_pruefen.py PROFIL --items 00-virtuelle-geraete/openhab/items
  python3 25-item-typen/profil_pruefen.py --tabelle          # Empfehlungen ausgeben
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "00-virtuelle-geraete"))

from gamepadsmarthome.actions import Profile                    # noqa: E402
from gamepadsmarthome.check import EMPFEHLUNG, check_profile, targets   # noqa: E402
from gamepadsmarthome.config import try_load_config             # noqa: E402


def items_from_files(directory: Path) -> dict:
    from mini_openhab import parse_items
    items = {}
    for p in sorted(directory.glob("**/*.items")):
        items.update(parse_items(p.read_text(encoding="utf-8")))
    return items


def items_from_openhab(url: str, token) -> dict:
    from openhab import Items, OpenHABClient
    data = Items(OpenHABClient(url=url, token=token)).getItems()
    if isinstance(data, dict):
        raise SystemExit(f"openHAB nicht erreichbar: {data}")
    return {i["name"]: i for i in data}


def main() -> int:
    ap = argparse.ArgumentParser(description="Bedienprofil prüfen")
    ap.add_argument("profil", nargs="?")
    ap.add_argument("--items", help="Ordner mit .items-Dateien statt openHAB")
    ap.add_argument("--url", help="openHAB-URL (Standard: config.yaml)")
    ap.add_argument("--liste", action="store_true", help="alle Ziel-Items anzeigen")
    ap.add_argument("--tabelle", action="store_true", help="Empfehlungstabelle anzeigen")
    args = ap.parse_args()
    if args.tabelle:
        for element, typen, befehl in EMPFEHLUNG:
            print(f"{element:<22} {typen:<30} {befehl}")
        return 0
    if not args.profil:
        ap.error("Profil angeben")
    profile = Profile.load(args.profil)
    if args.items:
        items = items_from_files(Path(args.items))
    else:
        oh = try_load_config().section("openhab")
        items = items_from_openhab(args.url or oh.get("url", "http://127.0.0.1:8080"), oh.get("token"))
    if args.liste:
        for item, value, kind in targets(profile):
            print(f"{kind:<8} {item:<45} {value}")
    errors = check_profile(Profile.load(args.profil), items)
    for e in errors:
        print("FEHLER", e)
    print(f"{profile.name}: {len(targets(Profile.load(args.profil)))} Ziele, {len(errors)} Fehler")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
