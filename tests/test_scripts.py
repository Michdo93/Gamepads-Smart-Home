"""Kapitelskripte, die ohne Controller laufen, einmal ausführen."""
import subprocess
import sys

from conftest import ROOT

REC = str(ROOT / "08-mapping/aufnahmen/labor_rundgang.jsonl")


def run(*args, timeout=60):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_offline_scripts():
    assert "Hysterese: 1" in run("09-analog/trigger_hysterese.py")
    assert "radial" in run("09-analog/deadzone_demo.py")
    assert "Farbton 180" in run("09-analog/farbkreis.py", "--replay", REC, "--speed", "50")
    out = run("10-bedienlogik/bedienlogik.py", "--replay", REC, "--speed", "5")
    assert "x:short" in out and "start:short" in out
    out = run("27-weitere-szenarien/ros2_cmd_vel.py", "--dry-run", "--ohne-totmann", "--replay", REC, "--speed", "20")
    assert "linear.x +0.249" in out


def test_profile_checker_cli():
    out = run("25-item-typen/profil_pruefen.py", "26-labor-szenarien/profile/labor.yaml",
              "--items", "00-virtuelle-geraete/openhab/items")
    assert "0 Fehler" in out


def test_usbip_port_parser(tmp_path):
    fake = tmp_path / "usbip"
    fake.write_text(f"#!/bin/sh\ncat {ROOT / '16-usbip/client/beispiel_usbip_port.txt'}\n")
    fake.chmod(0o755)
    env = {"PATH": f"{tmp_path}:/usr/bin:/bin"}
    port = lambda bid: subprocess.run(["bash", str(ROOT / "16-usbip/client/usbip-port.sh"), bid],  # noqa: E731
                                      capture_output=True, text=True, env=env).stdout.strip()
    assert port("1-1.2") == "0"
    assert port("1-1.21") == "1"
    assert port("1-1.3") == ""
