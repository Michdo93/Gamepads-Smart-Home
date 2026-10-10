"""
actions.py – Bedienprofile: welche Geste löst welchen openHAB-Befehl aus?

Ein Profil ist eine YAML-Datei (Kapitel 23 und 26). Beispiel:

    rings:                                  # Auswahllisten, im Text als {raum}, {sender}
      raum:   [iKonferenz, iKueche, iBad]
      sender: [SWR3, DASDING]
    lookups:                                # Tabelle je Ring-Eintrag, im Text als {lautstaerke}
      lautstaerke:
        ring: raum
        map: {iKonferenz: iKonferenz_Sonos_Playbar_Lautstaerke,
              iKueche: iKueche_Sonos_Lautsprecher_Lautstaerke, ...}
    actions:
      "x:short":   {toggle: iSmartHome_Hue_Lampen_Schalter}
      "up:press":  {command: "{raum}_Sonos_Lautsprecher_Lautstaerke", value: INCREASE}
      "up:repeat": {command: "{raum}_Sonos_Lautsprecher_Lautstaerke", value: INCREASE}
      "rb:short":  {ring: raum, step: 1, before: {command: "{raum}_Webradio_{sender}", value: "OFF"},
                                         after:  {command: "{raum}_Webradio_{sender}", value: "ON"}}
      "lstick:up":     {command: iSmartHome_Somfy_Rollladen_Steuerung, value: UP, group: links}
      "lstick:center": {stop: links}
    analog:
      rstick: {hue: iSmartHome_Hue_Lampen_Farbe, saturation: 100, brightness: 70}
      rt:     {dimmer: iSmartHome_Hue_Lampen_Helligkeit, step: 5}

Modi: Ein Profil kann mehrere Belegungen haben, zwischen denen eine Taste umschaltet:

    modes:
      licht: {actions: {...}, analog: {...}}
      tv:    {actions: {...}}
    actions:
      "guide:short": [{mode: next}, {feedback: led, value: "player_{modus_nr}"}]

Belegungen des aktiven Modus haben Vorrang vor den allgemeinen unter actions/analog.
Im Text stehen {modus} (Name) und {modus_nr} (1, 2, ...) zur Verfügung.

Aktionen (eine oder eine Liste je Geste):
  command  Befehl an ein Item              {command: Item, value: Wert}
  toggle   Switch umschalten               {toggle: Item}
  ring     Auswahl weiterschalten          {ring: Name, step: 1 | -1, before: ..., after: ...}
           carry: "{raum}_Webradio_{sender}" – läuft das Gerät (ON), zieht es mit um:
           altes Item OFF, neues Item ON
  stop     STOP an das zuletzt bewegte Item einer Gruppe   {stop: Gruppe}
  feedback Rückmeldung am Controller       {feedback: rumble | led, value: ...}
  mode     Modus wechseln                  {mode: next | prev | <Name>}

Profile.handle() liefert nur eine Liste von Operationen; ausgeführt werden sie vom
Executor (runtime.py). Dadurch ist die Logik ohne openHAB testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .analog import Quantizer, stick_to_hue
from .events import GamepadEvent
from .logic import Gesture, Ring


@dataclass(frozen=True)
class Op:
    kind: str            # "command" | "toggle" | "latest" | "carry" | "feedback"
    item: str            # bei feedback: rumble | led
    value: str = ""

    def __str__(self) -> str:
        return f"{self.kind:<8} {self.item} {self.value}".rstrip()


class _Fmt(dict):
    def __missing__(self, key):          # unbekannte Platzhalter stehen lassen
        return "{" + key + "}"


class Profile:
    def __init__(self, data: Dict[str, Any]):
        self.name = str(data.get("name", "Profil"))
        self.rings: Dict[str, Ring] = {n: Ring(v) for n, v in (data.get("rings") or {}).items()}
        self.actions = self._actions(data.get("actions"))
        self.lookups: Dict[str, dict] = dict(data.get("lookups") or {})
        self.analog: Dict[str, dict] = dict(data.get("analog") or {})
        self.modes: Dict[str, Dict[str, Any]] = {}
        for name, m in (data.get("modes") or {}).items():
            m = m or {}
            self.modes[str(name)] = {"actions": self._actions(m.get("actions")),
                                     "analog": dict(m.get("analog") or {})}
        self.mode = Ring(list(self.modes)) if self.modes else None
        self.moving: Dict[str, str] = {}               # Gruppe -> zuletzt bewegtes Item
        self._stick = {"lstick": [0.0, 0.0], "rstick": [0.0, 0.0]}
        self._quant: Dict[str, Quantizer] = {}
        self._last_hue: Dict[str, int] = {}

    @staticmethod
    def _actions(raw) -> Dict[str, List[dict]]:
        return {str(k): (v if isinstance(v, list) else [v]) for k, v in (raw or {}).items()}

    @property
    def current_mode(self) -> Optional[str]:
        return self.mode.current if self.mode else None

    def _lookup(self, table: str, key: str):
        if self.mode:
            found = self.modes[self.mode.current][table].get(key)
            if found is not None:
                return found
        return getattr(self, table).get(key)

    @classmethod
    def load(cls, path) -> "Profile":
        from .config import load_yaml
        return cls(load_yaml(path))

    # -- Platzhalter --------------------------------------------------------------------
    def fill(self, text: Union[str, int, float]) -> str:
        values = _Fmt({n: r.current for n, r in self.rings.items()})
        if self.mode:
            values["modus"], values["modus_nr"] = self.mode.current, str(self.mode.index + 1)
        for name, lk in self.lookups.items():
            current = self.rings[lk["ring"]].current
            values[name] = lk["map"].get(current, lk.get("default", ""))
        return str(text).format_map(values)

    # -- Gesten ----------------------------------------------------------------------------
    def handle(self, g: Gesture) -> List[Op]:
        ops: List[Op] = []
        for spec in self._lookup("actions", str(g)) or []:
            ops += self._run(spec)
        return ops

    def _run(self, spec: dict) -> List[Op]:
        if "command" in spec:
            item = self.fill(spec["command"])
            if "group" in spec:
                self.moving[str(spec["group"])] = item
            return [Op("command", item, self.fill(spec.get("value", "")))]
        if "toggle" in spec:
            return [Op("toggle", self.fill(spec["toggle"]))]
        if "stop" in spec:
            item = self.moving.pop(str(spec["stop"]), None)
            return [Op("command", item, "STOP")] if item else []
        if "ring" in spec:
            ring = self.rings[spec["ring"]]
            ops = self._many(spec.get("before"))
            old = self.fill(spec["carry"]) if "carry" in spec else None
            ring.next() if int(spec.get("step", 1)) > 0 else ring.prev()
            if old is not None:
                ops.append(Op("carry", old, self.fill(spec["carry"])))   # value = neues Item
            return ops + self._many(spec.get("after"))
        if "feedback" in spec:
            return [Op("feedback", str(spec["feedback"]), self.fill(spec.get("value", "")))]
        if "mode" in spec:
            if not self.mode:
                raise ValueError("Profil hat keine Modi")
            target = str(spec["mode"])
            self.mode.next() if target == "next" else self.mode.prev() if target == "prev" \
                else self.mode.select(target)
            self.moving.clear()
            return []
        raise ValueError(f"Unbekannte Aktion: {spec}")

    def _many(self, spec: Optional[Union[dict, List[dict]]]) -> List[Op]:
        if not spec:
            return []
        ops: List[Op] = []
        for s in (spec if isinstance(spec, list) else [spec]):
            ops += self._run(s)
        return ops

    # -- analoge Werte -----------------------------------------------------------------------
    def handle_analog(self, ev: GamepadEvent) -> List[Op]:
        if ev.kind != "axis":
            return []
        ops: List[Op] = []
        if ev.control in ("lt", "rt"):
            spec = self._lookup("analog", ev.control)
            if spec and "dimmer" in spec:
                q = self._quant.setdefault(ev.control, Quantizer(int(spec.get("step", 5))))
                pct = q.update(float(ev.value) * 100)  # type: ignore[arg-type]
                if pct is not None:
                    ops.append(Op("latest", self.fill(spec["dimmer"]), str(int(pct))))
        else:
            stick = "lstick" if ev.control in ("lx", "ly") else "rstick"
            xy = self._stick[stick]
            xy[0 if ev.control.endswith("x") else 1] = float(ev.value)  # type: ignore[arg-type]
            spec = self._lookup("analog", stick)
            if spec and "hue" in spec:
                hue = stick_to_hue(xy[0], xy[1], float(spec.get("deadzone", 0.5)), int(spec.get("step", 5)))
                if hue is not None and hue != self._last_hue.get(stick):
                    self._last_hue[stick] = hue
                    hsb = f"{hue},{spec.get('saturation', 100)},{spec.get('brightness', 70)}"
                    ops.append(Op("latest", self.fill(spec["hue"]), hsb))
        return ops
