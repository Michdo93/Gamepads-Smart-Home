import asyncio
import threading
import time

import paho.mqtt.client as mqtt

from conftest import ROOT, load_script
from gamepadsmarthome.config import Config
from gamepadsmarthome.events import GamepadEvent
from gamepadsmarthome.logic import Gesture
from gamepadsmarthome.mqtt import GamepadMqtt, GatewayEncoder

REC = str(ROOT / "08-mapping/aufnahmen/labor_rundgang.jsonl")


def test_encoder_throttle_and_flush():
    enc = GatewayEncoder("wz", rate_hz=10, step=5)
    assert enc.event(GamepadEvent("axis", "lx", 0.41, t=0.0)) == [("gamepad/wz/axis/lx", "40", True)]
    assert enc.event(GamepadEvent("axis", "lx", 0.62, t=0.02)) == []          # gedrosselt
    assert enc.event(GamepadEvent("axis", "lx", 0.81, t=0.04)) == []
    assert enc.flush(0.05) == []
    assert enc.flush(0.11) == [("gamepad/wz/axis/lx", "80", True)]            # letzter Wert kommt an
    assert enc.event(GamepadEvent("button", "a", 1, t=0.2)) == [("gamepad/wz/button/a", "ON", True)]
    assert enc.gesture(Gesture("a", "short")) == [("gamepad/wz/event", "a:short", False)]
    assert enc.event(GamepadEvent("dpad", "dpad", (1, 1), t=0.3)) == [("gamepad/wz/dpad", "UP_RIGHT", True)]


def test_gateway_dry_run(capsys):
    gw = load_script("18-mqtt-gateway/gamepad_mqtt_gateway.py", "gamepad_mqtt_gateway")
    sink = gw.PrintSink()
    w = gw.PadWorker("wz", Config(), sink, None, REC, speed=2)

    async def run():
        task = asyncio.create_task(w.run())
        while not task.done():
            w.tick(time.monotonic())
            await asyncio.sleep(0.01)

    asyncio.run(run())
    events = [p for t, p, r in sink.sent if t == "gamepad/wz/event"]
    for expected in ("x:short", "rb:short", "a:short", "up:repeat", "rt:press",
                     "lstick:up", "lstick:center", "start:short"):
        assert expected in events
    assert ("gamepad/wz/status", "online", True) in sink.sent
    hues = [p for t, p, r in sink.sent if t == "gamepad/wz/hue"]
    assert hues[-1] == "180"


def test_publish_and_feedback_via_broker(broker):
    received, ready = [], threading.Event()
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-sub")
    sub.on_connect = lambda c, u, f, rc, p: (c.subscribe("gamepad/#"), ready.set())
    sub.on_message = lambda c, u, m: received.append((m.topic, m.payload.decode(), m.retain))
    sub.connect("127.0.0.1", broker)
    sub.loop_start()
    assert ready.wait(5)

    gm = GamepadMqtt("127.0.0.1", broker, client_id="test-gw")
    feedback = []
    gm.on("gamepad/+/set/+", lambda t, p: feedback.append((t, p)))
    gm.start()
    for _ in range(50):
        if gm.client.is_connected():
            break
        time.sleep(0.1)
    time.sleep(0.3)
    gm.send([("gamepad/wz/event", "a:short", False), ("gamepad/wz/axis/lx", "40", True)])
    sub.publish("gamepad/wz/set/rumble", "klingel")
    for _ in range(50):
        if feedback and any(t == "gamepad/wz/event" for t, _, _ in received):
            break
        time.sleep(0.1)
    gm.stop()
    sub.loop_stop()
    assert ("gamepad/wz/event", "a:short", False) in received
    assert ("gamepad/gateway/status", "online", False) in received or \
        any(t == "gamepad/gateway/status" for t, _, _ in received)
    assert feedback == [("gamepad/wz/set/rumble", "klingel")]
