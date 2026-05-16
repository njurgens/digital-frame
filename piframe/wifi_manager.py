from __future__ import annotations

import logging
import subprocess
import threading

import pygame

from piframe import types
from piframe.types import WifiNetwork, WifiResult, WifiStatus


class WifiManager:
    """Wraps nmcli calls in daemon threads. Results posted via EVT_WIFI_RESULT."""

    def _post(self, result: WifiResult) -> None:
        try:
            if types.EVT_WIFI_RESULT is not None:
                pygame.event.post(pygame.event.Event(types.EVT_WIFI_RESULT, result=result))
        except Exception as e:
            logging.warning("EVT_WIFI_RESULT post failed: %s", e)

    def _run_cmd(self, cmd: str, timeout: int) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, str(e)

    def scan(self) -> None:
        def _thread() -> None:
            ok, output = self._run_cmd(
                "sudo nmcli -t -f SSID,SECURITY,SIGNAL dev wifi list",
                timeout=10,
            )
            if not ok:
                self._post(WifiResult("scan", False, error=output))
                return

            networks: list[WifiNetwork] = []
            for line in output.splitlines():
                parts = line.split(":")
                if len(parts) >= 3:
                    ssid = parts[0]
                    security = parts[1]
                    try:
                        signal = int(parts[2])
                    except ValueError:
                        signal = 0
                    if ssid:
                        networks.append(WifiNetwork(ssid=ssid, security=security, signal=signal))

            networks.sort(key=lambda n: n.signal, reverse=True)
            seen: dict[str, WifiNetwork] = {}
            for n in networks:
                if n.ssid not in seen:
                    seen[n.ssid] = n

            self._post(WifiResult("scan", True, data=list(seen.values())))

        threading.Thread(target=_thread, daemon=True).start()

    def connect(self, ssid: str, password: str | None) -> None:
        def _thread() -> None:
            if password:
                cmd = f"sudo nmcli dev wifi connect {ssid!r} password {password!r}"
            else:
                cmd = f"sudo nmcli dev wifi connect {ssid!r}"
            ok, output = self._run_cmd(cmd, timeout=15)
            self._post(WifiResult("connect", ok, error=None if ok else output))

        threading.Thread(target=_thread, daemon=True).start()

    def forget(self, ssid: str) -> None:
        def _thread() -> None:
            ok, output = self._run_cmd(f"sudo nmcli connection delete {ssid!r}", timeout=5)
            self._post(WifiResult("forget", ok, error=None if ok else output))

        threading.Thread(target=_thread, daemon=True).start()

    def disconnect(self) -> None:
        def _thread() -> None:
            ok, output = self._run_cmd("sudo nmcli dev disconnect wlan0", timeout=5)
            self._post(WifiResult("disconnect", ok, error=None if ok else output))

        threading.Thread(target=_thread, daemon=True).start()

    def get_status(self) -> None:
        def _thread() -> None:
            ok, output = self._run_cmd(
                "sudo nmcli -t -f GENERAL.CONNECTION,IP4.ADDRESS device show wlan0",
                timeout=5,
            )
            if not ok:
                self._post(WifiResult("status", False, error=output))
                return

            conn = ""
            ip = ""
            for line in output.splitlines():
                if line.startswith("GENERAL.CONNECTION:"):
                    conn = line.split(":", 1)[1].strip()
                elif line.startswith("IP4.ADDRESS[1]:"):
                    ip = line.split(":", 1)[1].strip()

            connected = bool(conn) and conn not in {"--", ""}
            status = WifiStatus(
                connected=connected,
                ssid=conn if connected else "",
                ip_address=ip if connected else "",
            )
            self._post(WifiResult("status", True, data=status))

        threading.Thread(target=_thread, daemon=True).start()
