# ============================================================================
# Kapitel 20 – Ansatz A: Gerätesteuerung über openHAB-Regeln (Python Scripting, openHAB 5)
# Datei: $OPENHAB_CONF/automation/python/gamepad_mqtt.py
# Nur EINE Sprachvariante (DSL, JS oder Python) gleichzeitig aktivieren!
# Belegung: siehe rules/gamepad_mqtt.rules
# ============================================================================

from openhab import rule, Registry
from openhab.triggers import when

import scope

EREIGNIS = "mqtt:topic:mosquitto:gamepad_wohnzimmer:event"
RAEUME = ["iKonferenz", "iKueche", "iBad", "iIoT", "iMultimedia"]
SENDER = ["SWR3", "bigFM_BW", "Energy_Stuttgart", "Radio_Regenbogen", "Antenne1", "DASDING"]
LAUTSTAERKE = {
    "iKonferenz": "iKonferenz_Sonos_Playbar_Lautstaerke",
    "iKueche": "iKueche_Sonos_Lautsprecher_Lautstaerke",
    "iBad": "iBad_Sonos_Lautsprecher_Lautstaerke",
    "iIoT": "iIoT_Sonos_Lautsprecher_Lautstaerke",
    "iMultimedia": "iMultimedia_Sonos_Lautsprecher_Lautstaerke",
}

_zuletzt_bewegt = None   # Rollladen/Jalousie, die der linke Stick zuletzt bewegt hat


def _text(name):
    return str(Registry.getItemState(name))


def _befehl(name, wert):
    Registry.getItem(name).sendCommand(wert)


def _umschalten(name):
    _befehl(name, scope.OFF if Registry.getItemState(name) == scope.ON else scope.ON)


def _radio(raum, sender):
    return f"{raum}_Webradio_{sender}"


def _weiter(liste, aktuell, schritt):
    i = liste.index(aktuell) if aktuell in liste else 0
    return liste[(i + schritt) % len(liste)]


def _auswahl(raum_schritt, sender_schritt):
    raum, sender = _text("Gamepad_Raum"), _text("Gamepad_Sender")
    radio = _radio(raum, sender)
    lauft = Registry.getItemState(radio) == scope.ON
    neu_raum = _weiter(RAEUME, raum, raum_schritt) if raum_schritt else raum
    neu_sender = _weiter(SENDER, sender, sender_schritt) if sender_schritt else sender
    Registry.getItem("Gamepad_Raum").postUpdate(neu_raum)
    Registry.getItem("Gamepad_Sender").postUpdate(neu_sender)
    if lauft:                                   # das Radio zieht mit um
        _befehl(radio, scope.OFF)
        _befehl(_radio(neu_raum, neu_sender), scope.ON)


def _bewegen(item, richtung):
    global _zuletzt_bewegt
    _zuletzt_bewegt = item
    _befehl(item, richtung)


def _stopp():
    global _zuletzt_bewegt
    if _zuletzt_bewegt:
        _befehl(_zuletzt_bewegt, "STOP")
    _zuletzt_bewegt = None


AKTIONEN = {
    "x:short": lambda: _umschalten("iSmartHome_Hue_Lampen_Schalter"),
    "b:short": lambda: _befehl("iSmartHome_Hue_Lampen_Farbtemperatur", "DECREASE"),
    "y:short": lambda: _befehl("iSmartHome_Hue_Lampen_Farbtemperatur", "INCREASE"),
    "left:press": lambda: _befehl("iSmartHome_Hue_Lampen_Helligkeit", "DECREASE"),
    "right:press": lambda: _befehl("iSmartHome_Hue_Lampen_Helligkeit", "INCREASE"),
    "up:press": lambda: _befehl(LAUTSTAERKE[_text("Gamepad_Raum")], "INCREASE"),
    "down:press": lambda: _befehl(LAUTSTAERKE[_text("Gamepad_Raum")], "DECREASE"),
    "a:short": lambda: _umschalten(_radio(_text("Gamepad_Raum"), _text("Gamepad_Sender"))),
    "lb:short": lambda: _auswahl(-1, 0),
    "rb:short": lambda: _auswahl(+1, 0),
    "lt:press": lambda: _auswahl(0, -1),
    "rt:press": lambda: _auswahl(0, +1),
    "lstick:up": lambda: _bewegen("iSmartHome_Somfy_Rollladen_Steuerung", "UP"),
    "lstick:down": lambda: _bewegen("iSmartHome_Somfy_Rollladen_Steuerung", "DOWN"),
    "lstick:right": lambda: _bewegen("iSmartHome_Jalousie_Steuerung", "UP"),
    "lstick:left": lambda: _bewegen("iSmartHome_Jalousie_Steuerung", "DOWN"),
    "lstick:center": _stopp,
    "start:short": lambda: _umschalten("iApplikation_Morgenroutine_Start"),
    "back:long": lambda: _umschalten("iApplikation_Morgenroutine_Ausgangszustand"),
}
for _r in ("left", "right", "up", "down"):               # Halten wiederholt wie ein Druck
    AKTIONEN[f"{_r}:repeat"] = AKTIONEN[f"{_r}:press"]


@rule()
@when("System started")
def gamepad_startwerte(module, input):
    if _text("Gamepad_Raum") in ("NULL", "UNDEF"):
        Registry.getItem("Gamepad_Raum").postUpdate("iMultimedia")
    if _text("Gamepad_Sender") in ("NULL", "UNDEF"):
        Registry.getItem("Gamepad_Sender").postUpdate("SWR3")


@rule()
@when(f"Channel {EREIGNIS} triggered")
def gamepad_ereignis(module, input):
    aktion = AKTIONEN.get(str(input["event"].getEvent()))
    if aktion:
        aktion()


@rule()
@when("Item Gamepad_Wohnzimmer_Farbton changed")
def gamepad_farbkreis(module, input):
    try:
        hue = Registry.getItemState("Gamepad_Wohnzimmer_Farbton").intValue()
    except AttributeError:                      # NULL oder UNDEF
        return
    _befehl("iSmartHome_Hue_Lampen_Farbe", f"{hue},100,70")
