// ============================================================================
// Kapitel 21 – Rückkanal: openHAB meldet sich am Controller (JavaScript Scripting)
// Datei: $OPENHAB_CONF/automation/js/gamepad_rueckkanal.js – Erklärung: rules/gamepad_rueckkanal.rules
// ============================================================================

const LED_RAUM = {
  iKonferenz: "player_1", iKueche: "player_2", iBad: "player_3", iIoT: "player_4", iMultimedia: "rotate",
};
const raumLed = () => LED_RAUM[items.Gamepad_Raum.state] ?? "player_1";

rules.when().item("iSmartHome_Klingel").changed().to("ON").then(() => {
  items.Gamepad_Wohnzimmer_Rumble.sendCommand("klingel");
}).build("Rückkanal: Klingel (JS)");

rules.when().item("iSmartHome_Alarm").changed().then((event) => {
  if (event.newState === "ON") {
    items.Gamepad_Wohnzimmer_Rumble.sendCommand("lang");
    items.Gamepad_Wohnzimmer_LED.sendCommand("blink_all_slow");
  } else {
    items.Gamepad_Wohnzimmer_LED.sendCommand(raumLed());
  }
}).build("Rückkanal: Alarm (JS)");

rules.when().item("Gamepad_Raum").changed()
  .or().item("Gamepad_Wohnzimmer_Online").changed().to("online")
  .then(() => {
    items.Gamepad_Wohnzimmer_LED.sendCommand(raumLed());
    items.Gamepad_Wohnzimmer_Rumble.sendCommand("kurz");
  }).build("Rückkanal: Raum anzeigen (JS)");
