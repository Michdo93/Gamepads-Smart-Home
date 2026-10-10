"""
mqtt.py – Ansatz A: Gamepad-Ereignisse über MQTT veröffentlichen (paho-mqtt >= 2.0).

Topic-Schema (base = "gamepad", alias aus config.yaml):

  <base>/gateway/status            online | offline            retained, Last Will
  <base>/<alias>/status            online | offline            retained (Controller verbunden?)
  <base>/<alias>/event             a:short, lb+up:repeat, lstick:up ...   Ereignis, NICHT retained
  <base>/<alias>/button/<name>     ON | OFF                    retained (Taste gehalten?)
  <base>/<alias>/dpad              UP | DOWN | LEFT | RIGHT | UP_LEFT ... | NONE
  <base>/<alias>/axis/<lx|ly|rx|ry>  -100 .. 100               retained, gedrosselt
  <base>/<alias>/axis/<lt|rt>        0 .. 100                  retained, gedrosselt
  <base>/<alias>/hue               0 .. 355 (rechter Stick als Farbkreis)
  <base>/<alias>/battery           0 .. 100                    (falls der Treiber ihn meldet)
  Rückkanal (openHAB -> Controller):
  <base>/<alias>/set/rumble        kurz | doppelt | lang | klingel | "stark,schwach,ms"
  <base>/<alias>/set/led           player_1 .. player_4 | rotate | off | "r,g,b"

GatewayEncoder macht aus Ereignissen MQTT-Nachrichten (ohne Netzwerk, testbar),
GamepadMqtt verschickt sie.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .analog import stick_to_hue
from .events import GamepadEvent, dpad_name
from .logic import Gesture

log = logging.getLogger("gamepadmqtt")

Message = Tuple[str, str, bool]          # (Topic, Payload, retained)


class GatewayEncoder:
    """
    Ereignisse -> Nachrichten. Achsen werden auf ganze Prozent gerundet, auf ein
    Raster gebracht (step) und höchstens rate_hz-mal je Sekunde gesendet. Der letzte
    Wert geht nie verloren: Was gedrosselt wurde, schickt flush() nach.
    """

    def __init__(self, alias: str, base: str = "gamepad", rate_hz: float = 10.0,
                 step: int = 5, hue_step: int = 5, hue_deadzone: float = 0.5):
        self.prefix = f"{base.rstrip('/')}/{alias}"
        self.interval = 1.0 / rate_hz if rate_hz > 0 else 0.0
        self.step, self.hue_step, self.hue_deadzone = step, hue_step, hue_deadzone
        self._sent: Dict[str, str] = {}
        self._sent_at: Dict[str, float] = {}
        self._pending: Dict[str, str] = {}
        self._stick = {"rx": 0.0, "ry": 0.0}

    def topic(self, *parts: str) -> str:
        return "/".join((self.prefix,) + parts)

    # -- Ereignisse -------------------------------------------------------------------
    def gesture(self, g: Gesture) -> List[Message]:
        return [(self.topic("event"), str(g), False)]

    def event(self, ev: GamepadEvent) -> List[Message]:
        out: List[Message] = []
        if ev.kind == "button":
            out += self._state(self.topic("button", ev.control), "ON" if ev.value else "OFF", ev.t, now=True)
        elif ev.kind == "dpad":
            out += self._state(self.topic("dpad"), dpad_name(ev.value).upper(), ev.t, now=True)  # type: ignore[arg-type]
        elif ev.kind == "axis":
            v = float(ev.value)  # type: ignore[arg-type]
            pct = int(round(v * 100 / self.step) * self.step)
            out += self._state(self.topic("axis", ev.control), str(pct), ev.t)
            if ev.control in self._stick:
                self._stick[ev.control] = v
                hue = stick_to_hue(self._stick["rx"], self._stick["ry"], self.hue_deadzone, self.hue_step)
                if hue is not None:
                    out += self._state(self.topic("hue"), str(hue), ev.t)
        return out

    def status(self, online: bool) -> List[Message]:
        payload = "online" if online else "offline"
        self._sent[self.topic("status")] = payload
        return [(self.topic("status"), payload, True)]

    def battery(self, percent: int) -> List[Message]:
        return self._state(self.topic("battery"), str(int(percent)), 0.0, now=True)

    def flush(self, now: float) -> List[Message]:
        """Gedrosselte Werte nachsenden – regelmäßig aufrufen (z. B. alle 50 ms)."""
        out: List[Message] = []
        for topic, payload in list(self._pending.items()):
            if now - self._sent_at.get(topic, -1e9) >= self.interval:
                del self._pending[topic]
                out += self._state(topic, payload, now, now=True)
        return out

    # -- intern ----------------------------------------------------------------------------
    def _state(self, topic: str, payload: str, t: float, now: bool = False) -> List[Message]:
        if self._sent.get(topic) == payload:
            self._pending.pop(topic, None)
            return []
        if not now and t - self._sent_at.get(topic, -1e9) < self.interval:
            self._pending[topic] = payload          # später nachsenden
            return []
        self._sent[topic] = payload
        self._sent_at[topic] = t
        self._pending.pop(topic, None)
        return [(topic, payload, True)]

    def retained(self) -> List[Message]:
        """Alle Zustände – nach einem Reconnect erneut senden."""
        return [(t, p, True) for t, p in self._sent.items()]


class GamepadMqtt:
    """Verbindung zum Broker mit Last Will, Reconnect und Rückkanal-Abo."""

    def __init__(self, host: str = "localhost", port: int = 1883,
                 username: Optional[str] = None, password: Optional[str] = None,
                 base_topic: str = "gamepad", client_id: str = "gamepad-gateway",
                 tls: bool = False):
        import paho.mqtt.client as mqtt
        self.base = base_topic.rstrip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password)
        if tls:
            self.client.tls_set()
        self.status_topic = f"{self.base}/gateway/status"
        self.client.will_set(self.status_topic, "offline", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._host, self._port = host, port
        self._retained: Dict[str, str] = {}
        self._handlers: List[Tuple[str, Callable[[str, str], None]]] = []

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "GamepadMqtt":
        return cls(host=cfg.get("host", "localhost"), port=int(cfg.get("port", 1883)),
                   username=cfg.get("username"), password=cfg.get("password"),
                   base_topic=cfg.get("base_topic", "gamepad"),
                   client_id=cfg.get("client_id", "gamepad-gateway"), tls=bool(cfg.get("tls", False)))

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("MQTT verbunden")
            client.publish(self.status_topic, "online", qos=1, retain=True)
            for topic, payload in self._retained.items():       # Zustände erneuern
                client.publish(topic, payload, qos=0, retain=True)
            for pattern, _ in self._handlers:
                client.subscribe(pattern, qos=1)
        else:
            log.error("MQTT-Verbindung abgelehnt: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        log.warning("MQTT getrennt (%s) – automatischer Reconnect", reason_code)

    def _on_message(self, client, userdata, msg):
        import paho.mqtt.client as mqtt
        payload = msg.payload.decode("utf-8", "replace").strip()
        for pattern, handler in self._handlers:
            if mqtt.topic_matches_sub(pattern, msg.topic):
                try:
                    handler(msg.topic, payload)
                except Exception:  # Fehler im Rückkanal dürfen das Gateway nicht beenden
                    log.exception("Fehler beim Verarbeiten von %s", msg.topic)

    def on(self, pattern: str, handler: Callable[[str, str], None]) -> None:
        """Rückkanal abonnieren, z. B. on('gamepad/+/set/#', handler)."""
        self._handlers.append((pattern, handler))
        if self.client.is_connected():
            self.client.subscribe(pattern, qos=1)

    def start(self) -> "GamepadMqtt":
        self.client.connect_async(self._host, self._port, keepalive=30)
        self.client.loop_start()
        return self

    def stop(self) -> None:
        self.client.publish(self.status_topic, "offline", qos=1, retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def send(self, messages: List[Message]) -> None:
        for topic, payload, retain in messages:
            if retain:
                self._retained[topic] = payload
            self.client.publish(topic, payload, qos=0, retain=retain)
