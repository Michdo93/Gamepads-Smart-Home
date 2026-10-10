#!/usr/bin/env bash
# Kapitel 17 – Mosquitto installieren und einrichten
#   sudo bash 17-mosquitto/setup_mosquitto.sh
# Fragt die Passwörter interaktiv ab (nichts landet in der Shell-Historie).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

apt-get install -y mosquitto mosquitto-clients
install -m 644 "$DIR/mosquitto/conf.d/gamepad.conf" /etc/mosquitto/conf.d/gamepad.conf
install -m 640 -o root -g mosquitto "$DIR/mosquitto/acl" /etc/mosquitto/acl

touch /etc/mosquitto/passwd
for user in gamepad openhab; do
    echo "Passwort für MQTT-Benutzer '$user':"
    mosquitto_passwd /etc/mosquitto/passwd "$user"
done
chown root:mosquitto /etc/mosquitto/passwd
chmod 640 /etc/mosquitto/passwd

systemctl enable mosquitto
systemctl restart mosquitto
systemctl --no-pager status mosquitto | head -5

cat <<'TXT'

Test in zwei Terminals:
  mosquitto_sub -h localhost -u openhab -P <passwort> -t 'gamepad/#' -v
  mosquitto_pub -h localhost -u gamepad -P <passwort> -t gamepad/test/event -m a:short
TXT
