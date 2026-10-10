// ============================================================================
// Kapitel 20 – Ansatz A: Gerätesteuerung über openHAB-Regeln (JavaScript Scripting, openHAB 5)
// Datei: $OPENHAB_CONF/automation/js/gamepad_mqtt.js
// Nur EINE Sprachvariante (DSL, JS oder Python) gleichzeitig aktivieren!
// Belegung: siehe rules/gamepad_mqtt.rules
// ============================================================================

const EREIGNIS = "mqtt:topic:mosquitto:gamepad_wohnzimmer:event";
const RAEUME = ["iKonferenz", "iKueche", "iBad", "iIoT", "iMultimedia"];
const SENDER = ["SWR3", "bigFM_BW", "Energy_Stuttgart", "Radio_Regenbogen", "Antenne1", "DASDING"];
const LAUTSTAERKE = {
  iKonferenz: "iKonferenz_Sonos_Playbar_Lautstaerke",
  iKueche: "iKueche_Sonos_Lautsprecher_Lautstaerke",
  iBad: "iBad_Sonos_Lautsprecher_Lautstaerke",
  iIoT: "iIoT_Sonos_Lautsprecher_Lautstaerke",
  iMultimedia: "iMultimedia_Sonos_Lautsprecher_Lautstaerke",
};

let zuletztBewegt = null;   // Rollladen/Jalousie, die der linke Stick zuletzt bewegt hat

const umschalten = (name) => {
  const item = items.getItem(name);
  item.sendCommand(item.state === "ON" ? "OFF" : "ON");
};
const radioItem = (raum, sender) => `${raum}_Webradio_${sender}`;
const weiter = (liste, aktuell, schritt) =>
  liste[(Math.max(0, liste.indexOf(aktuell)) + schritt + liste.length) % liste.length];
const bewegen = (item, befehl) => { zuletztBewegt = item; items.getItem(item).sendCommand(befehl); };

// Ereignis -> Aktion (Dispatch-Tabelle statt langer if-Kette)
const AKTIONEN = {
  "x:short": () => umschalten("iSmartHome_Hue_Lampen_Schalter"),
  "b:short": () => items.iSmartHome_Hue_Lampen_Farbtemperatur.sendCommand("DECREASE"),
  "y:short": () => items.iSmartHome_Hue_Lampen_Farbtemperatur.sendCommand("INCREASE"),
  "left:press": () => items.iSmartHome_Hue_Lampen_Helligkeit.sendCommand("DECREASE"),
  "right:press": () => items.iSmartHome_Hue_Lampen_Helligkeit.sendCommand("INCREASE"),
  "up:press": () => items.getItem(LAUTSTAERKE[items.Gamepad_Raum.state]).sendCommand("INCREASE"),
  "down:press": () => items.getItem(LAUTSTAERKE[items.Gamepad_Raum.state]).sendCommand("DECREASE"),
  "a:short": () => umschalten(radioItem(items.Gamepad_Raum.state, items.Gamepad_Sender.state)),
  "lb:short": () => auswahl(-1, 0),
  "rb:short": () => auswahl(+1, 0),
  "lt:press": () => auswahl(0, -1),
  "rt:press": () => auswahl(0, +1),
  "lstick:up": () => bewegen("iSmartHome_Somfy_Rollladen_Steuerung", "UP"),
  "lstick:down": () => bewegen("iSmartHome_Somfy_Rollladen_Steuerung", "DOWN"),
  "lstick:right": () => bewegen("iSmartHome_Jalousie_Steuerung", "UP"),
  "lstick:left": () => bewegen("iSmartHome_Jalousie_Steuerung", "DOWN"),
  "lstick:center": () => {
    if (zuletztBewegt) items.getItem(zuletztBewegt).sendCommand("STOP");
    zuletztBewegt = null;
  },
  "start:short": () => umschalten("iApplikation_Morgenroutine_Start"),
  "back:long": () => umschalten("iApplikation_Morgenroutine_Ausgangszustand"),
};
// Halten wiederholt wie ein kurzer Druck
for (const r of ["left", "right", "up", "down"]) AKTIONEN[`${r}:repeat`] = AKTIONEN[`${r}:press`];

function auswahl(raumSchritt, senderSchritt) {
  const raum = items.Gamepad_Raum.state;
  const sender = items.Gamepad_Sender.state;
  const radio = items.getItem(radioItem(raum, sender));
  const lauft = radio.state === "ON";
  const neuRaum = raumSchritt ? weiter(RAEUME, raum, raumSchritt) : raum;
  const neuSender = senderSchritt ? weiter(SENDER, sender, senderSchritt) : sender;
  items.Gamepad_Raum.postUpdate(neuRaum);
  items.Gamepad_Sender.postUpdate(neuSender);
  if (lauft) {                                   // das Radio zieht mit um
    radio.sendCommand("OFF");
    items.getItem(radioItem(neuRaum, neuSender)).sendCommand("ON");
  }
  console.info(`Auswahl: ${neuRaum} / ${neuSender}`);
}

rules.when().system().startLevel(100).then(() => {
  if (items.Gamepad_Raum.isUninitialized) items.Gamepad_Raum.postUpdate("iMultimedia");
  if (items.Gamepad_Sender.isUninitialized) items.Gamepad_Sender.postUpdate("SWR3");
}).build("Gamepad: Startwerte (JS)");

rules.when().channel(EREIGNIS).triggered().then((event) => {
  const aktion = AKTIONEN[event.receivedEvent];
  if (aktion) aktion();
}).build("Gamepad: Ereignisse (JS)");

rules.when().item("Gamepad_Wohnzimmer_Farbton").changed().then((event) => {
  const hue = parseInt(event.newState, 10);
  if (!Number.isNaN(hue)) items.iSmartHome_Hue_Lampen_Farbe.sendCommand(`${hue},100,70`);
}).build("Gamepad: rechter Stick als Farbkreis (JS)");
