import pygame

from gamepadsmarthome import codes as C
from gamepadsmarthome.backends.evdev_backend import EvdevTranslator
from gamepadsmarthome.backends.pygame_backend import GameControllerTranslator, PygameTranslator
from gamepadsmarthome.mapping import Mapping, available, find_mapping

XPAD_ABS = {0: (-32768, 32767), 1: (-32768, 32767), 2: (0, 255),
            3: (-32768, 32767), 4: (-32768, 32767), 5: (0, 255), 16: (-1, 1), 17: (-1, 1)}


def test_all_mappings_load_and_roundtrip(tmp_path):
    maps = available()
    assert {m.source.stem for m in maps} >= {"xbox360", "xbox360_wireless", "dualshock4", "standard"}
    for m in maps:
        assert set(m.evdev.buttons.values()) == {"a", "b", "x", "y", "lb", "rb", "back", "start",
                                                 "guide", "ls", "rs"}
        p = m.save(tmp_path / f"{m.source.stem}.yaml")
        again = Mapping.load(p)
        assert again.evdev.buttons == m.evdev.buttons
        assert again.pygame.axes.keys() == m.pygame.axes.keys()


def test_find_mapping():
    assert find_mapping("Xbox 360 Wireless Receiver (XBOX)").source.stem == "xbox360_wireless"
    assert find_mapping("Microsoft X-Box 360 pad").source.stem == "xbox360"
    assert find_mapping("irgendwas", 0x054C, 0x0BA0).source.stem == "dualshock4"
    assert find_mapping("Unbekannt").source.stem == "standard"


def test_xbox_vs_playstation_x_button():
    """Die linke Taste (x) meldet bei xpad BTN_NORTH (307), bei hid-playstation BTN_WEST (308)."""
    xbox, ds4 = Mapping.load("xbox360"), Mapping.load("dualshock4")
    assert xbox.evdev.buttons[C.CODES["BTN_NORTH"]] == "x"
    assert ds4.evdev.buttons[C.CODES["BTN_WEST"]] == "x"


def test_evdev_translator_wireless_dpad_buttons():
    tr = EvdevTranslator(Mapping.load("xbox360_wireless"), XPAD_ABS)
    out = tr.translate(C.EV_KEY, C.CODES["BTN_TRIGGER_HAPPY3"], 1, 0.0)
    assert [(e.kind, e.value) for e in out] == [("dpad", (0, 1))]
    out = tr.translate(C.EV_KEY, C.CODES["BTN_TRIGGER_HAPPY2"], 1, 0.1)
    assert out[0].value == (1, 1)
    assert tr.translate(C.EV_KEY, C.CODES["BTN_SOUTH"], 2, 0.2) == []   # Autorepeat ignorieren


def test_evdev_translator_axes_and_hat():
    tr = EvdevTranslator(Mapping.load("xbox360"), XPAD_ABS)
    assert tr.translate(C.EV_ABS, 1, -32768, 0)[0].value == 1.0         # Stick oben -> +1
    assert tr.translate(C.EV_ABS, 2, 255, 0)[0].value == 1.0            # LT durchgedrückt
    assert tr.translate(C.EV_ABS, 17, -1, 0)[0].value == (0, 1)         # Hat oben
    ds4 = EvdevTranslator(Mapping.load("dualshock4"), {0: (0, 255), 1: (0, 255)})
    assert ds4.translate(C.EV_ABS, 0, 255, 0)[0].value == 1.0


def test_pygame_translators():
    pygame.init()
    tr = PygameTranslator(Mapping.load("xbox360"))
    e = pygame.event.Event(pygame.JOYAXISMOTION, axis=2, value=-1.0, instance_id=0, joy=0)
    assert tr.translate(e)[0].control == "lt" and tr.translate(e)[0].value == 0.0
    e = pygame.event.Event(pygame.JOYAXISMOTION, axis=1, value=-1.0, instance_id=0, joy=0)
    assert tr.translate(e)[0].value == 1.0
    e = pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(0, 1), instance_id=0, joy=0)
    assert tr.translate(e)[0].value == (0, 1)
    wl = PygameTranslator(Mapping.load("xbox360_wireless"))
    e = pygame.event.Event(pygame.JOYBUTTONDOWN, button=13, instance_id=0, joy=0)
    assert wl.translate(e)[0].value == (0, 1)
    gc = GameControllerTranslator()
    e = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
                           value=32767, instance_id=0)
    assert gc.translate(e)[0].control == "rt" and gc.translate(e)[0].value == 1.0
    e = pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
                           instance_id=0)
    assert gc.translate(e)[0].value == (-1, 0)


def test_mapping_finder_detects(tmp_path):
    from conftest import load_script
    mf = load_script("08-mapping/mapping_finder.py", "mapping_finder")
    rest = {0: 0, 1: 0, 2: 0, 5: 0}
    ranges = {0: (-32768, 32767), 1: (-32768, 32767), 2: (0, 255), 5: (0, 255)}
    f = mf.Finder(rest, ranges)
    res = {}
    res["a"] = f.feed("button", ("key", 304, 1))
    assert f.feed("button", ("key", 304, 1)) is None              # schon vergeben
    assert f.feed("axis", ("abs", 0, 3000)) is None                # zu wenig
    res["lx"] = f.feed("axis", ("abs", 0, 30000))
    res["ly"] = f.feed("axis", ("abs", 1, -32000))                # nach oben = negativ
    res["lt"] = f.feed("trigger", ("abs", 2, 250))
    res["up"] = f.feed("dpad", ("hat", 17, 1))
    res["right"] = f.feed("dpad", ("hat", 16, 1))
    sec = mf.build_section(res, evdev=True)
    assert sec.buttons == {304: "a"}
    assert sec.axes[1].invert and not sec.axes[0].invert and sec.axes[2].trigger
    assert sec.hat == (16, 17)
