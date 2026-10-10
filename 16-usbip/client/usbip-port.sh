#!/usr/bin/env bash
# Gemeinsame USB/IP-Konfiguration der Reihe „Smart Home & …“ (Leap Motion, Gamepads, Kinect, NFC/RFID)
# Datei: /usr/local/sbin/usbip-port.sh
# Gibt die Nummer des virtuellen Ports aus, an dem die entfernte Bus-ID hängt
# (leer, wenn sie nicht verbunden ist). Ausgabe von "usbip port" z. B.:
#   Port 00: <Port in Use> at Full Speed(12Mbps)
#          Microsoft Corp. : Xbox 360 Wireless Adapter (045e:0719)
#          3-1 -> usbip://192.168.0.231:3240/1-1.2
# Verglichen wird die Bus-ID am Ende der usbip://-Adresse exakt (1-1.2 ist nicht 1-1.21).
BUS_ID="${1:?Aufruf: usbip-port.sh <bus-id>}"
USBIP="$(command -v usbip || echo /usr/sbin/usbip)"
"$USBIP" port 2>/dev/null | awk -v id="$BUS_ID" '
  /^Port [0-9]+:/ { p = $2; sub(":", "", p) }
  /usbip:\/\// { n = split($NF, a, "/"); if (a[n] == id) print p + 0 }'
