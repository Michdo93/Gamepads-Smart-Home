# Gamepads-Smart-Home

Begleit-Repository zum Buch **„Smart Home & Gamepads – Steuern Sie Ihr Zuhause mit Xbox- und
PlayStation-Controllern – mit openHAB, Python, MQTT und REST“** von Michael Christian Dörflinger.

Alle Beispiele laufen unter Linux (Raspberry Pi OS, Ubuntu) mit Python 3.9+ und openHAB 5.
Im Labor: Xbox-360-Controller mit Funkempfänger (und mit Kabel), DualShock 4 über den
Sony-USB-Funkadapter.

## Schnellstart

```bash
git clone https://github.com/Michdo93/Gamepads-Smart-Home.git
cd Gamepads-Smart-Home
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp config/config.example.yaml config/config.yaml      # Token, MQTT-Passwort eintragen
python3 05-installation/pruefen.py                      # ist alles bereit?
```

Ohne Controller und ohne openHAB lässt sich fast alles ausprobieren:

```bash
python3 00-virtuelle-geraete/mini_openhab.py &          # Mini-openHAB auf Port 8080
python3 23-rest-fernbedienung/fernbedienung.py --url http://127.0.0.1:8080 \
        --replay 08-mapping/aufnahmen/labor_rundgang.jsonl
python3 18-mqtt-gateway/gamepad_mqtt_gateway.py --dry-run \
        --replay 08-mapping/aufnahmen/labor_rundgang.jsonl
```

## Aufbau

| Ordner | Kapitel | Inhalt |
|---|---|---|
| `gamepadsmarthome/` | alle | Begleitbibliothek: Ereignisse, Mappings, Analogwerte, Bedienlogik, MQTT, REST, Profile |
| `gamepadsmarthome/mappings/` | 8, Anhang A | Mapping-Dateien: Xbox 360 (Kabel, Funk), DualShock 4, DualSense, Standard |
| `00-virtuelle-geraete/` | – | virtuelle Labor-Items, Sitemap, Hilfsregel, Mini-openHAB |
| `03-linux/` | 3 | udev-Regeln, Geräte auflisten |
| `04-bibliotheken/` | 4 | dieselbe Aufgabe mit evdev, pygame und inputs |
| `05-installation/` | 5 | Umgebung prüfen |
| `06-evdev/`, `07-pygame/` | 6, 7 | Rohdaten und logische Ereignisse |
| `08-mapping/` | 8 | Mapping-Finder, GameController-API, Aufnahme und Wiedergabe |
| `09-analog/`, `10-bedienlogik/` | 9, 10 | Deadzone, Farbkreis, Hysterese; kurz/lang/doppelt/halten/Ebenen |
| `11-rueckmeldung/` | 11 | Vibration, LEDs, Akku |
| `12-mehrere-controller/`, `13-robuster-betrieb/` | 12, 13 | Zuordnung per Alias, Reconnect, systemd |
| `14-linuxinput-binding/` | 14 | Versuch mit dem Linux Input Binding |
| `16-usbip/` | 16 | **gemeinsame USB/IP-Konfiguration der Reihe** |
| `17-mosquitto/` … `21-rueckkanal-mqtt/` | 17–21 | Ansatz A: MQTT, Things, Regeln (DSL, JS, Python), Rückkanal |
| `22-rest-grundlagen/` … `24-rest-async/` | 22–24 | Ansatz B: REST, Fernbedienung mit Profilen, Latenz, SSE |
| `25-item-typen/` | 25 | Profilprüfung: Items und Befehle |
| `26-labor-szenarien/`, `27-weitere-szenarien/` | 26, 27 | Profile: Labor mit 4 Modi, Kamera, Gäste, zwei Tasten, ROS 2 |
| `28-hybrid/` | 28 | REST und MQTT kombiniert |
| `tests/` | – | `pytest` – läuft ohne Hardware |

## Sicherheit

`config/config.yaml` steht in `.gitignore` und wird **nie** eingecheckt. API-Token und
MQTT-Passwörter gehören nur dorthin – nicht in Skripte, Things-Dateien oder Profile.

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

Die Tests brauchen weder Controller noch openHAB noch Mosquitto: Sie verwenden
Aufzeichnungen, das Mini-openHAB und einen kleinen MQTT-Broker in Python.
