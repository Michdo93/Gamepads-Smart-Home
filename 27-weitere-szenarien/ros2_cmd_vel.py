#!/usr/bin/env python3
"""
Kapitel 27 – Ausblick Robotik: der linke Stick fährt einen Roboter über ROS 2.

Linker Stick vor/zurück = Geschwindigkeit (linear.x), links/rechts = Drehung
(angular.z). Mit radialer Deadzone und Kennlinie, damit der Roboter in der
Mittelstellung wirklich steht und kleine Korrekturen möglich sind. LB ist ein
Totmannschalter: Nur solange LB gehalten wird, fährt der Roboter.

Voraussetzung: ROS 2 (rclpy, geometry_msgs) – getestet ist nur der Teil ohne ROS:
  python3 27-weitere-szenarien/ros2_cmd_vel.py --dry-run --replay 08-mapping/aufnahmen/labor_rundgang.jsonl

Aufruf:  python3 27-weitere-szenarien/ros2_cmd_vel.py [--topic /cmd_vel] [--max-v 0.3] [--max-w 1.0]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamepadsmarthome.analog import curve, deadzone_radial       # noqa: E402
from gamepadsmarthome.config import try_load_config              # noqa: E402
from gamepadsmarthome.source import add_source_args, open_source # noqa: E402


def geschwindigkeit(x: float, y: float, freigabe: bool, max_v: float, max_w: float):
    """Stick -> (linear.x m/s, angular.z rad/s). Ohne Freigabe: Stillstand."""
    if not freigabe:
        return 0.0, 0.0
    dx, dy = deadzone_radial(x, y, 0.15)
    v, w = round(curve(dy, 1.5) * max_v, 3), round(-curve(dx, 1.5) * max_w, 3)   # rechts = negativ drehen
    return v + 0.0, w + 0.0                                                     # -0.0 vermeiden


def main() -> int:
    ap = argparse.ArgumentParser(description="Gamepad -> ROS 2 /cmd_vel")
    ap.add_argument("--topic", default="/cmd_vel")
    ap.add_argument("--max-v", type=float, default=0.3)
    ap.add_argument("--max-w", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true", help="ohne ROS 2, nur ausgeben")
    ap.add_argument("--ohne-totmann", action="store_true", help="LB nicht verlangen (nur Simulation!)")
    add_source_args(ap)
    args = ap.parse_args()

    publish = None
    if not args.dry_run:
        import rclpy
        from geometry_msgs.msg import Twist
        rclpy.init()
        node = rclpy.create_node("gamepad_teleop")
        pub = node.create_publisher(Twist, args.topic, 10)

        def publish(v, w):  # noqa: F811 – ersetzt das None von oben
            msg = Twist()
            msg.linear.x, msg.angular.z = v, w
            pub.publish(msg)

    xy, freigabe, last = [0.0, 0.0], args.ohne_totmann, None
    for ev in open_source(args, try_load_config()).events():
        if ev.control in ("lx", "ly"):
            xy[0 if ev.control == "lx" else 1] = ev.value
        elif ev.control == "lb" and not args.ohne_totmann:
            freigabe = bool(ev.value)
        else:
            continue
        cmd = geschwindigkeit(xy[0], xy[1], freigabe, args.max_v, args.max_w)
        if cmd != last:
            last = cmd
            print(f"{time.strftime('%H:%M:%S')}  linear.x {cmd[0]:+.3f}  angular.z {cmd[1]:+.3f}")
            if publish:
                publish(*cmd)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
