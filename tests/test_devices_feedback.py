import os
from pathlib import Path

from gamepadsmarthome.devices import PadInfo, assign, is_gamepad
from gamepadsmarthome.feedback import battery, find_leds, set_led


def test_is_gamepad():
    assert is_gamepad({1: [304, 305, 315], 3: [(0, None), (1, None)]})
    assert not is_gamepad({1: [30, 31, 32]})                       # Tastatur
    assert not is_gamepad({1: [304], 3: [(16, None)]})            # nur Hat, kein ABS_X


def test_assign_wireless_slots():
    pads = [PadInfo(f"/dev/input/event{n}", "Xbox 360 Wireless Receiver (XBOX)",
                    f"usb-0000:01:00.0-1.2/input{slot}", "", 0x045E, 0x0719)
            for n, slot in ((7, 0), (9, 2))]
    pads.append(PadInfo("/dev/input/event11", "Sony Interactive Entertainment Wireless Controller",
                        "usb-0000:01:00.0-1.3/input3", "a4:ae:12:00:00:01", 0x054C, 0x0BA0))
    rules = [{"alias": "wohnzimmer", "name": "Xbox 360 Wireless", "phys": "input0"},
             {"alias": "labor", "name": "Xbox 360 Wireless", "phys": "input2"},
             {"alias": "ps4", "usb": "054c:"},
             {"alias": "fehlt", "uniq": "00:11:22"}]
    got = assign(pads, rules)
    assert got["wohnzimmer"].path.endswith("event7")
    assert got["labor"].path.endswith("event9")
    assert got["ps4"].uniq.startswith("a4:ae")
    assert "fehlt" not in got


def fake_sysfs(tmp: Path, event="event7") -> Path:
    """Nachgebauter sysfs-Baum: input-Gerät mit LEDs und Akku beim HID-Gerät."""
    hid = tmp / "devices/usb1/1-1/1-1:1.0/0003:054C:0BA0.0001"
    inp = hid / "input/input20"
    (inp).mkdir(parents=True)
    (tmp / "class/input" / event).mkdir(parents=True)
    os.symlink(inp, tmp / "class/input" / event / "device")
    led = hid / "leds/input20:rgb:indicator"
    led.mkdir(parents=True)
    (led / "multi_intensity").write_text("0 0 0")
    (led / "brightness").write_text("0")
    ps = hid / "power_supply/ps-controller-battery-a4:ae:12:00:00:01"
    ps.mkdir(parents=True)
    (ps / "capacity").write_text("85\n")
    (ps / "status").write_text("Discharging\n")
    return led


def test_leds_and_battery(tmp_path):
    led = fake_sysfs(tmp_path)
    assert list(find_leds("/dev/input/event7", str(tmp_path))) == ["input20:rgb:indicator"]
    assert set_led("/dev/input/event7", "255,0,0", str(tmp_path)) == ["input20:rgb:indicator"]
    assert (led / "multi_intensity").read_text() == "255 0 0"
    assert battery("/dev/input/event7", str(tmp_path)) == (85, "Discharging")
    assert set_led("/dev/input/event7", "player_2", str(tmp_path)) == []      # keine Xbox-LED
