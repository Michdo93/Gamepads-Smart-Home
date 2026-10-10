"""Die Python-Regeln (Kapitel 20, 21) mit nachgebauten openHAB-Modulen ausführen."""
import sys
import types

import pytest

from conftest import load_script


class State:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.v)

    def __str__(self):
        return str(self.v)

    def intValue(self):
        return int(self.v)


class Item:
    def __init__(self, reg, name):
        self.reg, self.name = reg, name

    def sendCommand(self, v):
        self.reg.log.append((self.name, str(v)))
        self.reg.states[self.name] = str(v)

    def postUpdate(self, v):
        self.reg.states[self.name] = str(v)


class Registry:
    states, log = {}, []

    @classmethod
    def getItem(cls, name):
        return Item(cls, name)

    @classmethod
    def getItemState(cls, name):
        v = cls.states.get(name, "NULL")
        if v == "NULL":
            return "NULL"
        return State(v)


@pytest.fixture
def oh(monkeypatch):
    rules = []
    openhab = types.ModuleType("openhab")
    openhab.Registry = Registry
    openhab.rule = lambda *a, **k: (lambda f: (rules.append(f), f)[1])
    triggers = types.ModuleType("openhab.triggers")
    triggers.when = lambda *a, **k: (lambda f: f)
    scope = types.ModuleType("scope")
    scope.ON, scope.OFF = "ON", "OFF"
    monkeypatch.setitem(sys.modules, "openhab", openhab)
    monkeypatch.setitem(sys.modules, "openhab.triggers", triggers)
    monkeypatch.setitem(sys.modules, "scope", scope)
    Registry.states, Registry.log = {}, []
    return Registry


class Ev:
    def __init__(self, e):
        self.e = e

    def getEvent(self):
        return self.e


def test_gamepad_rules(oh):
    m = load_script("20-mqtt-rules/openhab/automation/python/gamepad_mqtt.py", "gamepad_mqtt_rules")
    m.gamepad_startwerte(None, {})
    assert oh.states["Gamepad_Raum"] == "iMultimedia"
    fire = lambda e: m.gamepad_ereignis(None, {"event": Ev(e)})   # noqa: E731
    fire("x:short")
    assert oh.states["iSmartHome_Hue_Lampen_Schalter"] == "ON"
    fire("a:short")                                               # Radio an
    assert oh.states["iMultimedia_Webradio_SWR3"] == "ON"
    fire("rb:short")                                              # nächster Raum: Radio zieht mit
    assert oh.states["Gamepad_Raum"] == "iKonferenz"
    assert oh.states["iMultimedia_Webradio_SWR3"] == "OFF"
    assert oh.states["iKonferenz_Webradio_SWR3"] == "ON"
    fire("up:repeat")
    assert oh.log[-1] == ("iKonferenz_Sonos_Playbar_Lautstaerke", "INCREASE")
    fire("lstick:center")                                         # nichts bewegt
    fire("lstick:left")
    fire("lstick:center")
    assert oh.log[-2:] == [("iSmartHome_Jalousie_Steuerung", "DOWN"), ("iSmartHome_Jalousie_Steuerung", "STOP")]
    oh.states["Gamepad_Wohnzimmer_Farbton"] = "120"
    m.gamepad_farbkreis(None, {})
    assert oh.log[-1] == ("iSmartHome_Hue_Lampen_Farbe", "120,100,70")


def test_rueckkanal_rules(oh):
    m = load_script("21-rueckkanal-mqtt/openhab/automation/python/gamepad_rueckkanal.py", "gamepad_rk")
    oh.states["Gamepad_Raum"] = "iKueche"
    m.rueckkanal_raum(None, {})
    assert ("Gamepad_Wohnzimmer_LED", "player_2") in oh.log
    oh.states["iSmartHome_Alarm"] = "ON"
    m.rueckkanal_alarm(None, {})
    assert oh.log[-1] == ("Gamepad_Wohnzimmer_LED", "blink_all_slow")
