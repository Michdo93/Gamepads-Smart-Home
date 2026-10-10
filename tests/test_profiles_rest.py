import asyncio

import pytest

from conftest import ROOT
from gamepadsmarthome.actions import Op, Profile
from gamepadsmarthome.backends import replay
from gamepadsmarthome.check import check_profile, targets
from gamepadsmarthome.events import GamepadEvent
from gamepadsmarthome.logic import ControlLogic, Gesture
from gamepadsmarthome.rest import OpenHABSender
from gamepadsmarthome.runtime import Executor, run_controller

PROFILES = sorted(ROOT.glob("2[3-7]-*/profile/*.yaml"))
REC = ROOT / "08-mapping/aufnahmen/labor_rundgang.jsonl"


def virtual_items():
    from mini_openhab import create_server
    return create_server().items


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.name)
def test_profiles_match_virtual_items(path):
    profile = Profile.load(path)
    assert targets(profile)
    assert check_profile(Profile.load(path), virtual_items()) == []


def test_checker_finds_errors():
    p = Profile({"actions": {"a:short": {"command": "iSmartHome_Hue_Lampen_Schalter", "value": "INCREASE"},
                             "b:short": {"command": "iSmartHome_Somfy_Rollladen_Steuerung", "value": "ON"},
                             "x:short": {"toggle": "Gibt_es_nicht"}}})
    errors = check_profile(p, virtual_items())
    assert len(errors) == 3


def test_profile_modes_and_lookups():
    p = Profile.load(ROOT / "26-labor-szenarien/profile/labor.yaml")
    assert p.current_mode == "licht"
    assert [str(o) for o in p.handle(Gesture("a", "short"))] == ["toggle   iSmartHome_Hue_Lampen_Schalter"]
    ops = p.handle(Gesture("guide", "short"))
    assert p.current_mode == "radio"
    assert Op("feedback", "led", "player_2") in ops
    p.handle(Gesture("rb", "short"))                         # nächster Radioraum
    up = p.handle(Gesture("up", "press"))
    assert up == [Op("command", "iKonferenz_Sonos_Playbar_Lautstaerke", "INCREASE")]


def test_stop_group():
    p = Profile.load(ROOT / "23-rest-fernbedienung/profile/xbox360_original.yaml")
    assert p.handle(Gesture("lstick", "center")) == []       # nichts bewegt -> kein STOP
    p.handle(Gesture("lstick", "left"))
    assert p.handle(Gesture("lstick", "center")) == [Op("command", "iSmartHome_Jalousie_Steuerung", "STOP")]


def test_analog_hue_and_trigger():
    p = Profile.load(ROOT / "26-labor-szenarien/profile/labor.yaml")
    assert p.handle_analog(GamepadEvent("axis", "rx", 0.9)) == [Op("latest", "iSmartHome_Hue_Lampen_Farbe", "90,100,70")]
    assert p.handle_analog(GamepadEvent("axis", "rt", 0.42)) == [Op("latest", "iSmartHome_Hue_Lampen_Helligkeit", "40")]
    assert p.handle_analog(GamepadEvent("axis", "rt", 0.41)) == []      # Raster 5: wieder 40


def test_replay_against_mini_openhab(mini_oh):
    url, srv = mini_oh
    profile = Profile.load(ROOT / "23-rest-fernbedienung/profile/xbox360_original.yaml")

    async def run():
        async with OpenHABSender(url) as sender:
            ex = Executor(sender, 0.02).start()
            events = replay.async_play(replay.load(REC), speed=4)
            await run_controller(events, ControlLogic(), profile, ex)
            await asyncio.sleep(0.5)
            await ex.drain()
            await ex.stop()

    asyncio.run(run())
    st = {n: i["state"] for n, i in srv.items.items()}
    assert st["iSmartHome_Hue_Lampen_Schalter"] == "ON"
    assert st["iSmartHome_Hue_Lampen_Helligkeit"] == "10"            # INCREASE von 0
    assert st["iKueche_Webradio_SWR3"] == "OFF"                      # Sender gewechselt ...
    assert st["iKueche_Webradio_bigFM_BW"] == "ON"                   # ... Radio zieht mit
    assert st["iSmartHome_Hue_Lampen_Farbe"] == "180,100,70"         # letzter Farbton gewinnt
    assert st["iApplikation_Morgenroutine_Start"] == "ON"
    cmds = [c for c in srv.commands if c[0] == "iSmartHome_Somfy_Rollladen_Steuerung"]
    assert cmds == [("iSmartHome_Somfy_Rollladen_Steuerung", "UP"), ("iSmartHome_Somfy_Rollladen_Steuerung", "STOP")]


def test_sse_watch(mini_oh):
    url, srv = mini_oh

    async def run():
        async with OpenHABSender(url) as sender:
            async def change():
                await asyncio.sleep(0.5)
                await sender.send("iSmartHome_Klingel", "ON", force=True)
            task = asyncio.create_task(change())
            async for item, state in sender.watch_states(["iSmartHome_Klingel"]):
                await task
                return item, state

    assert asyncio.run(asyncio.wait_for(run(), 10)) == ("iSmartHome_Klingel", "ON")
