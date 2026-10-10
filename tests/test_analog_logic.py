from gamepadsmarthome.analog import (Quantizer, RateLimiter, StickDirection, TriggerSwitch,
                                     deadzone_axial, deadzone_radial, normalize, normalize_trigger,
                                     polar, stick_to_hue)
from gamepadsmarthome.events import GamepadEvent
from gamepadsmarthome.logic import ControlLogic, Ring


def test_normalize():
    assert normalize(-32768, -32768, 32767) == -1.0
    assert abs(normalize(0, -32768, 32767)) < 0.001
    assert normalize(0, 0, 255, invert=True) == 1.0          # DS4: oben = 0 -> +1
    assert normalize_trigger(255, 0, 255) == 1.0
    assert normalize_trigger(-1.0, -1.0, 1.0) == 0.0


def test_deadzones():
    assert deadzone_axial(0.1, 0.15) == 0.0
    assert abs(deadzone_axial(1.0, 0.15) - 1.0) < 1e-9
    assert abs(deadzone_axial(-0.575, 0.15) + 0.5) < 1e-9
    x, y = deadzone_radial(0.1, 0.1, 0.15)                   # r = 0.141 < 0.15
    assert (x, y) == (0.0, 0.0)
    x, y = deadzone_radial(0.12, 0.0, 0.1)                   # axial wäre 0.022 auf x
    assert x > 0 and y == 0.0


def test_polar_and_hue():
    assert polar(0, 1)[0] == 0.0          # oben
    assert polar(1, 0)[0] == 90.0         # rechts
    assert polar(0, -1)[0] == 180.0
    assert stick_to_hue(0.2, 0.2) is None              # zu wenig ausgelenkt
    assert stick_to_hue(-1, 0) == 270
    assert stick_to_hue(0.7, 0.7, step=5) == 45


def test_trigger_hysteresis():
    t = TriggerSwitch(0.6, 0.4)
    seq = [0.5, 0.61, 0.55, 0.45, 0.62, 0.39, 0.5]
    assert [t.update(v) for v in seq] == [None, True, None, None, None, False, None]


def test_stick_direction():
    d = StickDirection()
    assert d.update(0, 0.5) is None
    assert d.update(0, 0.7) == "UP"
    assert d.update(0.1, 0.5) is None        # über "off" -> bleibt UP
    assert d.update(0.8, 0.1) == "RIGHT"     # Wechsel ohne Mitte
    assert d.update(0.1, 0.1) == "CENTER"


def test_quantizer_and_rate():
    q = Quantizer(5)
    assert q.update(41) == 40 and q.update(42) is None and q.update(48) == 50
    now = [0.0]
    r = RateLimiter(0.1, clock=lambda: now[0])
    assert r.allow("x") and not r.allow("x")
    now[0] = 0.11
    assert r.allow("x")


def ev(kind, control, value, t):
    return GamepadEvent(kind, control, value, "p", t)


def names(gestures):
    return [str(g) for g in gestures]


def test_short_long_double():
    lg = ControlLogic(long_press=0.5, double_press=0.3)
    assert names(lg.feed(ev("button", "a", 1, 0.0))) == ["a:press"]
    assert names(lg.feed(ev("button", "a", 0, 0.1))) == ["a:release", "a:short"]
    assert names(lg.feed(ev("button", "a", 1, 0.2))) == ["a:press"]
    assert names(lg.feed(ev("button", "a", 0, 0.3))) == ["a:release", "a:short", "a:double"]
    lg.feed(ev("button", "b", 1, 1.0))
    assert names(lg.tick(1.4)) == []
    assert names(lg.tick(1.6)) == ["b:long"]
    assert names(lg.feed(ev("button", "b", 0, 2.0))) == ["b:release"]      # kein short nach long


def test_repeat_and_dpad():
    lg = ControlLogic(repeat_delay=0.4, repeat_interval=0.1)
    assert names(lg.feed(ev("dpad", "dpad", (0, 1), 0.0))) == ["up:press"]
    assert names(lg.tick(0.35)) == []
    assert names(lg.tick(0.62)) == ["up:repeat", "up:repeat", "up:repeat"]
    assert names(lg.feed(ev("dpad", "dpad", (1, 0), 0.7))) == ["up:release", "right:press"]


def test_modifier_layer():
    lg = ControlLogic(modifiers=["lb"])
    lg.feed(ev("button", "lb", 1, 0.0))
    assert names(lg.feed(ev("button", "a", 1, 0.1))) == ["lb+a:press"]
    assert names(lg.feed(ev("button", "a", 0, 0.2))) == ["lb+a:release", "lb+a:short"]
    assert names(lg.feed(ev("button", "lb", 0, 0.3))) == ["lb:release"]    # Ebenentaste: kein short


def test_trigger_and_stick_gestures():
    lg = ControlLogic()
    assert names(lg.feed(ev("axis", "rt", 0.7, 0.0))) == ["rt:press"]
    assert names(lg.feed(ev("axis", "rt", 0.5, 0.05))) == []
    assert names(lg.feed(ev("axis", "rt", 0.2, 0.1))) == ["rt:release", "rt:short"]
    assert names(lg.feed(ev("axis", "ly", -0.9, 0.2))) == ["lstick:down"]
    assert names(lg.feed(ev("axis", "ly", 0.0, 0.3))) == ["lstick:center"]


def test_ring():
    r = Ring(["a", "b", "c"])
    assert r.next() == "b" and r.prev() == "a" and r.prev() == "c"
