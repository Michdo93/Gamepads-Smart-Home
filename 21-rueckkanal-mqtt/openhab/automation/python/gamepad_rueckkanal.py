# ============================================================================
# Kapitel 21 – Rückkanal: openHAB meldet sich am Controller (Python Scripting)
# Datei: $OPENHAB_CONF/automation/python/gamepad_rueckkanal.py – Erklärung: rules/gamepad_rueckkanal.rules
# ============================================================================

from openhab import rule, Registry
from openhab.triggers import when

import scope

LED_RAUM = {"iKonferenz": "player_1", "iKueche": "player_2", "iBad": "player_3",
            "iIoT": "player_4", "iMultimedia": "rotate"}


def _senden(item, wert):
    Registry.getItem(item).sendCommand(wert)


def _raum_led():
    return LED_RAUM.get(str(Registry.getItemState("Gamepad_Raum")), "player_1")


@rule()
@when("Item iSmartHome_Klingel changed to ON")
def rueckkanal_klingel(module, input):
    _senden("Gamepad_Wohnzimmer_Rumble", "klingel")


@rule()
@when("Item iSmartHome_Alarm changed")
def rueckkanal_alarm(module, input):
    if Registry.getItemState("iSmartHome_Alarm") == scope.ON:
        _senden("Gamepad_Wohnzimmer_Rumble", "lang")
        _senden("Gamepad_Wohnzimmer_LED", "blink_all_slow")
    else:
        _senden("Gamepad_Wohnzimmer_LED", _raum_led())


@rule()
@when("Item Gamepad_Raum changed")
@when("Item Gamepad_Wohnzimmer_Online changed to online")
def rueckkanal_raum(module, input):
    _senden("Gamepad_Wohnzimmer_LED", _raum_led())
    _senden("Gamepad_Wohnzimmer_Rumble", "kurz")
