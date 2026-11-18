#!/usr/bin/env python3
"""
OpenCartaZero — Native Focus V Carta Sport & Carta 2 BLE Controller for M5Stack Cardputer Zero
320x170 RGB565 Framebuffer UI + Raw Evdev Keyboard + BlueZ D-Bus GATT Client
License: GPL-3.0-or-later
"""

import collections
import datetime
import json
import math
import os
import select
import signal
import struct
import sys
import threading
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.modules["pkg_resources"] = type(
    "P", (), {"resource_stream": lambda *_: None, "resource_exists": lambda *_: False}
)()
import pygame

try:
    import gi
    from gi.repository import Gio, GLib
    HAS_GIO = True
except Exception:
    HAS_GIO = False

# ==============================================================================
# DISPLAY & THEME CONSTANTS (Exact OpenCarta Theme)
# ==============================================================================
W, H = 320, 170

BG = (0, 0, 0)               # #000000
SURFACE = (17, 19, 20)       # #111314
ELEVATED = (24, 27, 29)      # #181B1D
BORDER = (35, 39, 42)        # #23272A
MINT = (30, 215, 166)        # #1ED7A6
MINT_DIM = (19, 141, 109)    # #138D6D
MINT_DARK = (10, 52, 42)
TEXT = (255, 255, 255)       # #FFFFFF
SUBTEXT = (138, 144, 148)    # #8A9094
MUTED = (85, 91, 96)         # #555B60
DANGER = (255, 82, 82)       # #FF5252
WARN = (255, 176, 32)        # #FFB020
BLUE = (88, 166, 255)        # #58A6FF

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
KBD_DEV = "/dev/input/by-path/platform-3f804000.i2c-event"
CONFIG_DIR = os.path.expanduser("~/.config/opencartazero")
CURVES_FILE = os.path.join(CONFIG_DIR, "curves.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

# ==============================================================================
# LINUX INPUT EVDEV KEYCODES
# ==============================================================================
KEY_ESC = 1
KEY_1, KEY_2, KEY_3, KEY_4, KEY_5 = 2, 3, 4, 5, 6
KEY_6, KEY_7, KEY_8, KEY_9, KEY_0 = 7, 8, 9, 10, 11
KEY_MINUS = 12
KEY_EQUAL = 13
KEY_BACKSPACE = 14
KEY_TAB = 15
KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T = 16, 17, 18, 19, 20
KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P = 21, 22, 23, 24, 25
KEY_LEFTBRACE = 26
KEY_RIGHTBRACE = 27
KEY_ENTER = 28
KEY_A, KEY_S, KEY_D, KEY_F, KEY_G = 30, 31, 32, 33, 34
KEY_H, KEY_J, KEY_K, KEY_L = 35, 36, 37, 38
KEY_SEMICOLON = 39
KEY_APOSTROPHE = 40
KEY_LEFTSHIFT = 42
KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B = 44, 45, 46, 47, 48
KEY_N, KEY_M = 49, 50
KEY_COMMA = 51
KEY_DOT = 52
KEY_SLASH = 53
KEY_RIGHTSHIFT = 54
KEY_SPACE = 57
KEY_UP = 103
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_DOWN = 108

KEY_TO_CHAR = {
    KEY_1: "1", KEY_2: "2", KEY_3: "3", KEY_4: "4", KEY_5: "5",
    KEY_6: "6", KEY_7: "7", KEY_8: "8", KEY_9: "9", KEY_0: "0",
    KEY_Q: "q", KEY_W: "w", KEY_E: "e", KEY_R: "r", KEY_T: "t",
    KEY_Y: "y", KEY_U: "u", KEY_I: "i", KEY_O: "o", KEY_P: "p",
    KEY_A: "a", KEY_S: "s", KEY_D: "d", KEY_F: "f", KEY_G: "g",
    KEY_H: "h", KEY_J: "j", KEY_K: "k", KEY_L: "l",
    KEY_Z: "z", KEY_X: "x", KEY_C: "c", KEY_V: "v", KEY_B: "b",
    KEY_N: "n", KEY_M: "m", KEY_SPACE: " ", KEY_MINUS: "-",
    KEY_EQUAL: "=", KEY_LEFTBRACE: "[", KEY_RIGHTBRACE: "]",
    KEY_SEMICOLON: ";", KEY_APOSTROPHE: "'",
    KEY_DOT: ".", KEY_COMMA: ",", KEY_SLASH: "/",
}

KEY_TO_CHAR_SHIFT = {
    KEY_1: "!", KEY_2: "@", KEY_3: "#", KEY_4: "$", KEY_5: "%",
    KEY_6: "^", KEY_7: "&", KEY_8: "*", KEY_9: "(", KEY_0: ")",
    KEY_Q: "Q", KEY_W: "W", KEY_E: "E", KEY_R: "R", KEY_T: "T",
    KEY_Y: "Y", KEY_U: "U", KEY_I: "I", KEY_O: "O", KEY_P: "P",
    KEY_A: "A", KEY_S: "S", KEY_D: "D", KEY_F: "F", KEY_G: "G",
    KEY_H: "H", KEY_J: "J", KEY_K: "K", KEY_L: "L",
    KEY_Z: "Z", KEY_X: "X", KEY_C: "C", KEY_V: "V", KEY_B: "B",
    KEY_N: "N", KEY_M: "M", KEY_SPACE: " ", KEY_MINUS: "_",
    KEY_EQUAL: "+", KEY_LEFTBRACE: "{", KEY_RIGHTBRACE: "}",
    KEY_SEMICOLON: ":", KEY_APOSTROPHE: '"',
    KEY_DOT: ">", KEY_COMMA: "<", KEY_SLASH: "?",
}

# ==============================================================================
# CARTA BLE PROTOCOL CONSTANTS & PACKET BUILDERS
# ==============================================================================
CARTA_SERVICE_UUID = "1011123e-8535-b5a0-7140-a304d2495cb7"
CARTA_NOTIFY_UUID  = "1011123e-8535-b5a0-7140-a304d2495cb8"
CARTA_WRITE_UUID   = "1011123e-8535-b5a0-7140-a304d2495cb9"
DIS_MODEL_UUID     = "00002a24-0000-1000-8000-00805f9b34fb"
DIS_SERIAL_UUID    = "00002a25-0000-1000-8000-00805f9b34fb"
DIS_FW_UUID        = "00002a28-0000-1000-8000-00805f9b34fb"
TELINK_MFG_ID      = 0x0211

LED_MODES = [
    (0x13, "ROTATE"),
    (0x23, "PULSE"),
    (0x33, "FADE"),
    (0x43, "SPARKLE"),
    (0x53, "STATIC"),
]

COLOR_PALETTE = [
    (0x1ED7A6, "Mint"),
    (0x00F028, "Green"),
    (0x00A8FF, "Cyan"),
    (0x0000F9, "Blue"),
    (0x8A2BE2, "Purple"),
    (0xFF00AA, "Magenta"),
    (0xFF2020, "Red"),
    (0xFF8800, "Orange"),
    (0xFFE600, "Yellow"),
    (0xFFFFFF, "White"),
]


def c_to_f(c: int) -> int:
    return int(round(c * 9.0 / 5.0 + 32.0))


def f_to_c(f: int) -> int:
    return int(round((f - 32.0) * 5.0 / 9.0))


def rgb_tuple(rgb_int: int) -> tuple[int, int, int]:
    return ((rgb_int >> 16) & 0xFF, (rgb_int >> 8) & 0xFF, rgb_int & 0xFF)


def to_hex(data: bytes | list[int]) -> str:
    return " ".join(f"{b & 0xFF:02x}" for b in data)


def parse_carta_adv(data: bytes | list[int] | None) -> dict | None:
    if not data or len(data) < 8:
        return None
    raw = bytes(data)
    if raw[0] != ord("{") or raw[-1] != ord("}"):
        return None
    try:
        pipe_idx = raw.index(ord("|"))
        tilde_idx = raw.index(ord("~"))
        caret_idx = raw.index(ord("^"))
        if pipe_idx <= 1 or tilde_idx <= pipe_idx + 1 or caret_idx != tilde_idx + 2:
            return None
        model = raw[1:pipe_idx].decode("ascii", errors="ignore").strip()
        serial = raw[pipe_idx + 1 : tilde_idx].decode("ascii", errors="ignore").strip()
        bat = raw[tilde_idx + 1]
        return {
            "model": model or None,
            "serial": serial or None,
            "battery": bat if 0 <= bat <= 100 else None,
        }
    except ValueError:
        return None


def pkt_time_sync_utc() -> bytes:
    now = datetime.datetime.now(datetime.timezone.utc)
    yr = now.year
    return bytes([
        0xDD, 0x0C,
        (yr >> 8) & 0xFF, yr & 0xFF,
        now.month, now.day, now.hour, now.minute,
        0x00, 0x00, 0x00,
        0xDD,
    ])


def pkt_settings_11(
    unit_byte: int,
    brightness: int,
    heat_preset: int,
    led_preset: int,
    vibe_level: int,
    low_power: bool,
    power_byte: int = 0x00,
) -> bytes:
    return bytes([
        0x11, 0x0C,
        power_byte & 0xFF,
        unit_byte & 0xFF,
        max(0x02, min(0x0A, brightness)),
        0x00,
        max(1, min(5, heat_preset)),
        max(0, min(5, led_preset)),
        0x00,
        max(0x02, min(0x0A, vibe_level)),
        0x01 if low_power else 0x00,
        0x11,
    ])


def pkt_preset_table_66(presets: dict[int, tuple[int, int]], unit_byte: int) -> bytes:
    out = bytearray([0x66, 0x13])
    default_t = 446 if unit_byte == 0x11 else 230
    for slot in range(1, 6):
        t, sec = presets.get(slot, (default_t, 55))
        tc = max(50, min(650, int(t)))
        sc = max(10, min(240, int(sec)))
        out.extend([(tc >> 8) & 0xFF, tc & 0xFF, sc & 0xFF])
    out.append(unit_byte & 0xFF)
    out.append(0x66)
    return bytes(out)


def pkt_cc_command(
    herb_temp: int,
    wax_temp: int,
    unit_byte: int,
    herb_timer: int,
    wax_timer: int,
    preset_slot: int,
    action_byte: int,
) -> bytes:
    ht = max(50, min(650, int(herb_temp)))
    wt = max(100, min(650, int(wax_temp)))
    htm = max(10, min(240, int(herb_timer)))
    wtm = max(10, min(120, int(wax_timer)))
    return bytes([
        0xCC, 0x10,
        (ht >> 8) & 0xFF, ht & 0xFF,
        (wt >> 8) & 0xFF, wt & 0xFF,
        unit_byte & 0xFF,
        (htm >> 8) & 0xFF, htm & 0xFF,
        (wtm >> 8) & 0xFF, wtm & 0xFF,
        0x00,
        max(0, min(5, preset_slot)),
        action_byte & 0xFF,
        0x00,
        0xCC,
    ])


def pkt_timeouts_d1(led_sec: int, sleep_sec: int) -> bytes:
    ls = max(60, min(900, int(led_sec)))
    ss = max(60, min(900, int(sleep_sec)))
    return bytes([
        0xD1, 0x07,
        (ls >> 8) & 0xFF, ls & 0xFF,
        (ss >> 8) & 0xFF, ss & 0xFF,
        0xD1,
    ])


def pkt_rename(new_name: str) -> tuple[bytes, bytes]:
    raw = new_name.strip().encode("utf-8")[:29]
    p1 = bytearray(20)
    p1[0] = 0xAC
    p1[1] = 0x14
    p1[2 : 2 + min(17, len(raw))] = raw[:17]
    p1[19] = 0xAC

    p2 = bytearray(15)
    p2[0] = 0xAF
    p2[1] = 0x0F
    if len(raw) > 17:
        rem = raw[17:29]
        p2[2 : 2 + len(rem)] = rem
    p2[14] = 0xAF
    return bytes(p1), bytes(p2)


def pkt_led_config(slot: int, mode_byte: int, colors: list[int]) -> bytes:
    s = max(1, min(5, slot))
    op = 0xE0 + (s - 1)
    pkt = bytearray(20)
    pkt[0] = op
    pkt[1] = 0x14
    pkt[2] = 0xAA
    pkt[3] = mode_byte & 0xFF
    for i in range(5):
        rgb = colors[i] if i < len(colors) else 0x1ED7A6
        pkt[4 + i * 3] = (rgb >> 16) & 0xFF
        pkt[5 + i * 3] = (rgb >> 8) & 0xFF
        pkt[6 + i * 3] = rgb & 0xFF
    pkt[19] = op
    return bytes(pkt)


# ==============================================================================
# TEMPERATURE CURVES REPOSITORY
# ==============================================================================
BUILTIN_CURVES = [
    {
        "id": "quartz_cooling",
        "name": "Quartz Banger Cooling (55s)",
        "mode": "smooth",
        "desc": "Starts at 245°C (473°F) to melt cleanly, decays exponentially to 215°C (419°F) for terp-rich pulls.",
        "pointsC": [(0, 245), (8, 237), (18, 230), (30, 223), (42, 218), (55, 215)],
    },
    {
        "id": "rosin_ladder",
        "name": "Live Rosin Terp Ladder (55s)",
        "mode": "step",
        "desc": "Connoisseur steps: 210°C (monoterpenes), 222°C (mid-spectrum body), 235°C (clean finish).",
        "pointsC": [(0, 210), (18, 222), (38, 235), (55, 235)],
    },
    {
        "id": "cold_start_ramp",
        "name": "Cold-Start Smooth Ramp (55s)",
        "mode": "smooth",
        "desc": "Continuous ascending ramp (205°C -> 235°C) sweeping gently through terpene boiling points.",
        "pointsC": [(0, 205), (20, 217), (40, 228), (55, 235)],
    },
    {
        "id": "resin_cloud",
        "name": "Live Resin Flavor -> Cloud (50s)",
        "mode": "step",
        "desc": "Starts at 220°C for bright terps, steps to 232°C for vapor, finishes at 245°C to clear.",
        "pointsC": [(0, 220), (15, 232), (35, 245), (50, 245)],
    },
    {
        "id": "flash_mellow",
        "name": "Flash Melt -> Mellow Finish (55s)",
        "mode": "smooth",
        "desc": "Starts at 240°C for quick initial melt, then coasts down to 212°C for smooth backend pulls.",
        "pointsC": [(0, 240), (12, 228), (30, 219), (55, 212)],
    },
]

GEN_SHAPES = [
    ("exp", "Exponential Decay"),
    ("linear", "Linear Ramp"),
    ("ladder", "3-Step Terp Ladder"),
    ("ease_in", "Flavor Hold -> Ramp"),
]


def eval_curve_temp_c(points_c: list[tuple[int, int]], mode: str, elapsed_sec: float) -> int:
    pts = sorted(points_c, key=lambda x: x[0])
    if not pts:
        return 230
    if elapsed_sec <= pts[0][0]:
        return pts[0][1]
    if elapsed_sec >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        t0, c0 = pts[i]
        t1, c1 = pts[i + 1]
        if t0 <= elapsed_sec < t1:
            if mode == "step" or t1 == t0:
                return c0
            frac = (elapsed_sec - t0) / float(t1 - t0)
            return int(round(c0 + frac * (c1 - c0)))
    return pts[-1][1]


# ==============================================================================
# CARTA STATE & BLUEZ D-BUS BLE MANAGER
# ==============================================================================
class CartaBleManager:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.bus = None
        if HAS_GIO:
            try:
                self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            except Exception:
                self.bus = None

        # Connection & Discovery State
        self.status = "DISCONNECTED"  # DISCONNECTED, SCANNING, CONNECTING, CONNECTED
        self.show_all_ble = False
        self.scanned_devices: list[dict] = []
        self.device_path: str | None = None
        self.write_char_path: str | None = None
        self.notify_char_path: str | None = None
        self.sub_id: int | None = None
        self.user_disconnected = True
        self.last_known_dev: dict | None = self._load_saved_device()
        self.last_connected_at: float = float(self.last_known_dev.get("last_connected_at", 0.0)) if self.last_known_dev else 0.0
        self.was_clean_exit: bool = bool(self.last_known_dev.get("clean_exit", True)) if self.last_known_dev else True
        self.disconnect_at: float = 0.0
        self.next_reconnect_at: float = 0.0
        self.reconnect_attempts: int = 0
        self.last_rx_at: float = 0.0
        self.write_queue: collections.deque = collections.deque()
        self.write_event = threading.Event()
        self._connect_lock = threading.Lock()

        # Device Identity
        self.device_name = "Carta Sport"
        self.device_address = ""
        self.model_number = "S3BL"
        self.serial_number = "--"
        self.firmware_version = "--"

        # Live Telemetry (0x99)
        self.unit_byte = 0x22  # 0x22 = °C, 0x11 = °F
        self.current_temp = 20
        self.herb_temp = 165
        self.wax_temp = 230
        self.remaining_sec = 0
        self.battery_percent = 0
        self.is_charging = False
        self.has_atomizer = True
        self.active_heat_preset = 1
        self.is_manual_heat = False
        self.active_led_preset = 5
        self.led_brightness = 8
        self.herb_timer_sec = 180
        self.wax_timer_sec = 55
        self.vibe_level = 8
        self.low_power_mode = False
        self.standby_countdown = 0

        # Dab Counters (0xaa)
        self.dab_counter_1 = 0
        self.dab_counter_2 = 0
        self.dab_counter_3 = 0
        self.dab_counter_4 = 0

        # Timeouts (0xd2)
        self.led_timeout_sec = 480
        self.sleep_timeout_sec = 600

        # Stored Preset Tables
        self.preset_tables_rx: set[int] = set()
        self.presets_c = {
            1: (230, 55),
            2: (257, 55),
            3: (268, 50),
            4: (279, 50),
            5: (296, 45),
        }
        self.presets_f = {
            1: (446, 55),
            2: (495, 55),
            3: (514, 50),
            4: (534, 50),
            5: (565, 45),
        }
        self.herb_presets_c = {
            1: (165, 180),
            2: (175, 180),
            3: (185, 180),
            4: (195, 180),
            5: (205, 180),
        }
        self.herb_presets_f = {
            1: (329, 180),
            2: (347, 180),
            3: (365, 180),
            4: (383, 180),
            5: (401, 180),
        }
        self.led_presets = {
            1: {"mode": 0x13, "colors": [0x00F028, 0xFF0000, 0x0000FF, 0x1ED7A6, 0xFFFFFF]},
            2: {"mode": 0x23, "colors": [0x00F028, 0xFF0000, 0x0000FF, 0x00FFAA, 0xFFAA00]},
            3: {"mode": 0x33, "colors": [0x00F028, 0xFF0000, 0x0000FF, 0xAA00FF, 0x00AAFF]},
            4: {"mode": 0x43, "colors": [0x00F028, 0xFF0000, 0x0000FF, 0xFF00AA, 0xAAFF00]},
            5: {"mode": 0x13, "colors": [0x00F028, 0x0000F9, 0x00F413, 0x0800E1, 0x0FE300]},
        }
        self._restore_saved_presets()

        # Logs & Callbacks
        self.logs: collections.deque = collections.deque(maxlen=60)
        self.hide_spam_logs = True
        self.last_99_key = ""
        self.on_telemetry_cb = None
        self.on_connected_cb = None

        # Background GLib loop for D-Bus signals + serialized GATT writer + watchdog
        self._loop = None
        if HAS_GIO and self.bus:
            self._subscribe_signals()
            threading.Thread(target=self._glib_thread, daemon=True).start()
            threading.Thread(target=self._writer_loop, daemon=True).start()
            threading.Thread(target=self._watchdog_loop, daemon=True).start()

    def _load_saved_device(self) -> dict | None:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if d.get("path") and d.get("address"):
                        return d
        except Exception:
            pass
        return None

    def _restore_saved_presets(self) -> None:
        d = self.last_known_dev
        if not d:
            return
        try:
            if "presets_c" in d:
                self.presets_c = {int(k): (int(v[0]), int(v[1])) for k, v in d["presets_c"].items()}
            if "presets_f" in d:
                self.presets_f = {int(k): (int(v[0]), int(v[1])) for k, v in d["presets_f"].items()}
            if "unit_byte" in d and d["unit_byte"] in (0x11, 0x22):
                self.unit_byte = int(d["unit_byte"])
            if "active_heat_preset" in d:
                self.active_heat_preset = max(1, min(5, int(d["active_heat_preset"])))
            tbl = self.presets_f if self.is_fahrenheit else self.presets_c
            if self.active_heat_preset in tbl:
                self.wax_temp, self.wax_timer_sec = tbl[self.active_heat_preset]
        except Exception:
            pass

    def _save_device(
        self,
        dev_info: dict,
        last_connected_at: float | None = None,
        clean_exit: bool = False,
    ) -> None:
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            ts = self.last_connected_at if last_connected_at is None else last_connected_at
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "path": dev_info["path"],
                        "address": dev_info["address"],
                        "name": dev_info["name"],
                        "is_carta": True,
                        "last_connected_at": ts,
                        "clean_exit": clean_exit,
                        "unit_byte": self.unit_byte,
                        "active_heat_preset": self.active_heat_preset,
                        "presets_c": {str(k): list(v) for k, v in self.presets_c.items()},
                        "presets_f": {str(k): list(v) for k, v in self.presets_f.items()},
                    },
                    f,
                )
        except Exception:
            pass

    def mark_clean_exit(self) -> None:
        self.user_disconnected = True
        if self.last_known_dev:
            self._save_device(self.last_known_dev, last_connected_at=self.last_connected_at, clean_exit=True)

    def _writer_loop(self) -> None:
        while True:
            self.write_event.wait(0.25)
            self.write_event.clear()
            while True:
                with self.lock:
                    if not self.write_queue:
                        break
                    pkt, label = self.write_queue.popleft()
                if not self.is_connected or not self.bus or not self.write_char_path:
                    continue
                try:
                    v_bytes = GLib.Variant("ay", list(pkt))
                    v_opts = GLib.Variant("a{sv}", {"type": GLib.Variant("s", "command")})
                    self.bus.call_sync(
                        "org.bluez",
                        self.write_char_path,
                        "org.bluez.GattCharacteristic1",
                        "WriteValue",
                        GLib.Variant.new_tuple(v_bytes, v_opts),
                        None,
                        Gio.DBusCallFlags.NONE,
                        1800,
                        None,
                    )
                except Exception as e:
                    self.add_log("INFO", f"Write err: {e}")
                time.sleep(0.065)

    def _watchdog_loop(self) -> None:
        while True:
            time.sleep(1.5)
            now = time.time()
            # 1) If connected, verify 0x99 telemetry is still flowing
            if self.status == "CONNECTED" and self.notify_char_path and self.bus:
                if self.last_rx_at > 0 and (now - self.last_rx_at) > 2.2:
                    # Fallback poll Value + re-assert StartNotify
                    try:
                        res = self.bus.call_sync(
                            "org.bluez",
                            self.notify_char_path,
                            "org.freedesktop.DBus.Properties",
                            "Get",
                            GLib.Variant("(ss)", ("org.bluez.GattCharacteristic1", "Value")),
                            None,
                            Gio.DBusCallFlags.NONE,
                            1000,
                            None,
                        )
                        val = bytes(res.unpack()[0])
                        if val:
                            self._handle_notification(val)
                    except Exception:
                        pass
                    if (now - self.last_rx_at) > 4.0:
                        try:
                            self.bus.call_sync(
                                "org.bluez",
                                self.notify_char_path,
                                "org.bluez.GattCharacteristic1",
                                "StartNotify",
                                None,
                                None,
                                Gio.DBusCallFlags.NONE,
                                1500,
                                None,
                            )
                        except Exception:
                            pass

            # 2) If unexpectedly disconnected (not user-initiated), auto-reconnect with backoff & 2m decay
            elif (
                self.status == "DISCONNECTED"
                and not self.user_disconnected
                and self.last_known_dev
                and not self._connect_lock.locked()
                and self.disconnect_at > 0
            ):
                if (now - self.disconnect_at) > 120.0:
                    self.user_disconnected = True
                    self.disconnect_at = 0.0
                    self.reconnect_attempts = 0
                    self.add_log("INFO", "Auto-reconnect decayed (2m timeout)")
                elif now >= self.next_reconnect_at:
                    delay = min(30.0, 3.0 * (2 ** self.reconnect_attempts))
                    self.reconnect_attempts += 1
                    self.next_reconnect_at = now + delay
                    self.add_log("INFO", f"Auto-reconnecting to Carta (try #{self.reconnect_attempts})...")
                    self.connect_device(self.last_known_dev, is_auto=True)

    @property
    def is_connected(self) -> bool:
        return self.status == "CONNECTED"

    @property
    def is_fahrenheit(self) -> bool:
        return self.unit_byte == 0x11

    @property
    def unit_str(self) -> str:
        return "°F" if self.is_fahrenheit else "°C"

    @property
    def is_session_active(self) -> bool:
        return self.remaining_sec > 0

    @property
    def is_preheating(self) -> bool:
        return self.remaining_sec > 0 and self.current_temp < self.wax_temp - 2

    def add_log(self, direction: str, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        with self.lock:
            self.logs.append((ts, direction, msg))

    def _glib_thread(self) -> None:
        try:
            ctx = GLib.MainContext.default()
            while True:
                ctx.iteration(True)
        except Exception:
            pass

    def _subscribe_signals(self) -> None:
        if not self.bus:
            return
        self.sub_id = self.bus.signal_subscribe(
            "org.bluez",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_properties_changed,
            None,
        )

    def _on_properties_changed(
        self, conn, sender, path, iface, signal_name, params, user_data
    ) -> None:
        try:
            unpacked = params.unpack()
            changed_iface = unpacked[0]
            changed_props = unpacked[1]
            if path == self.notify_char_path and changed_iface == "org.bluez.GattCharacteristic1":
                if "Value" in changed_props:
                    self._handle_notification(bytes(changed_props["Value"]))
            elif path == self.device_path and changed_iface == "org.bluez.Device1":
                if "Connected" in changed_props and not changed_props["Connected"]:
                    was_connected = self.status == "CONNECTED"
                    self.status = "DISCONNECTED"
                    self.remaining_sec = 0
                    if was_connected and not self.user_disconnected:
                        now = time.time()
                        self.disconnect_at = now
                        self.reconnect_attempts = 0
                        self.next_reconnect_at = now + 3.0
                        if self.last_known_dev:
                            self._save_device(self.last_known_dev, last_connected_at=now, clean_exit=False)
                    self.add_log("INFO", "Disconnected from device")
        except Exception:
            pass

    def _get_managed_objects(self) -> dict:
        if not self.bus:
            return {}
        try:
            res = self.bus.call_sync(
                "org.bluez",
                "/",
                "org.freedesktop.DBus.ObjectManager",
                "GetManagedObjects",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            )
            return res.unpack()[0]
        except Exception:
            return {}

    def start_scan(self) -> None:
        if not self.bus:
            self.add_log("INFO", "BlueZ D-Bus unavailable")
            return
        if self._connect_lock.locked():
            self.add_log("INFO", "Busy connecting, scan skipped")
            return
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        self.status = "SCANNING"
        self.add_log("INFO", "Scanning for Carta BLE devices...")
        try:
            # Ensure adapter powered
            self.bus.call_sync(
                "org.bluez",
                "/org/bluez/hci0",
                "org.freedesktop.DBus.Properties",
                "Set",
                GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered", GLib.Variant("b", True))),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
            try:
                self.bus.call_sync(
                    "org.bluez",
                    "/org/bluez/hci0",
                    "org.bluez.Adapter1",
                    "SetDiscoveryFilter",
                    GLib.Variant("(a{sv})", ({"Transport": GLib.Variant("s", "le")},)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
            except Exception:
                pass
            try:
                self.bus.call_sync(
                    "org.bluez",
                    "/org/bluez/hci0",
                    "org.bluez.Adapter1",
                    "StartDiscovery",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
            except Exception:
                pass

            for _ in range(10):
                if self.status != "SCANNING":
                    break
                self.refresh_scanned_devices()
                time.sleep(0.5)
        except Exception as e:
            self.add_log("INFO", f"Scan error: {e}")
        finally:
            try:
                self.bus.call_sync(
                    "org.bluez",
                    "/org/bluez/hci0",
                    "org.bluez.Adapter1",
                    "StopDiscovery",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
            except Exception:
                pass
            if self.status == "SCANNING":
                self.refresh_scanned_devices()
                self.status = "DISCONNECTED"

    def stop_scan(self) -> None:
        if not self.bus:
            return
        try:
            self.bus.call_sync(
                "org.bluez",
                "/org/bluez/hci0",
                "org.bluez.Adapter1",
                "StopDiscovery",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
        except Exception:
            pass
        if self.status == "SCANNING":
            self.status = "DISCONNECTED"

    def refresh_scanned_devices(self) -> None:
        objs = self._get_managed_objects()
        found = []
        for path, ifaces in objs.items():
            dev = ifaces.get("org.bluez.Device1")
            if not dev:
                continue
            addr = dev.get("Address", "")
            raw_name = (dev.get("Name") or dev.get("Alias") or "").replace("\x00", "").strip()
            rssi = dev.get("RSSI")
            if rssi is None and not dev.get("Connected", False):
                continue
            if rssi is None:
                rssi = -60
            uuids = [u.lower() for u in dev.get("UUIDs", [])]
            mfg = dev.get("ManufacturerData", {})
            telink_bytes = mfg.get(TELINK_MFG_ID) or mfg.get(str(TELINK_MFG_ID))
            parsed_adv = parse_carta_adv(telink_bytes)

            is_carta = (
                parsed_adv is not None
                or CARTA_SERVICE_UUID in uuids
                or raw_name.lower().startswith("pfeifi")
                or raw_name.lower().startswith("carta")
                or raw_name.lower().startswith("focus")
                or addr.lower().startswith("a4:c1:38")
            )
            if not self.show_all_ble and not is_carta:
                continue

            disp_name = raw_name if raw_name and raw_name != addr.replace(":", "-") else (
                "Carta Sport" if is_carta else f"BLE ({addr[-5:]})"
            )
            found.append({
                "path": path,
                "address": addr,
                "name": disp_name,
                "rssi": rssi,
                "is_carta": is_carta,
                "battery": parsed_adv["battery"] if parsed_adv else None,
                "model": parsed_adv["model"] if parsed_adv else None,
                "serial": parsed_adv["serial"] if parsed_adv else None,
            })

        found.sort(key=lambda d: (1 if d["is_carta"] else 0, d["rssi"]), reverse=True)
        with self.lock:
            self.scanned_devices = found

    def connect_device(self, dev_info: dict, is_auto: bool = False) -> None:
        if not self.bus:
            return
        self.user_disconnected = False
        self.last_known_dev = dict(dev_info)
        if not is_auto:
            self.disconnect_at = 0.0
            self.reconnect_attempts = 0
            self.next_reconnect_at = 0.0
        self.stop_scan()
        threading.Thread(target=self._connect_worker, args=(dev_info, is_auto), daemon=True).start()

    def _connect_worker(self, dev_info: dict, is_auto: bool = False) -> None:
        if not self._connect_lock.acquire(blocking=False):
            return
        try:
            path = dev_info["path"]
            self.device_path = path
            self.device_address = dev_info["address"]
            self.device_name = dev_info["name"]
            if dev_info.get("model"):
                self.model_number = dev_info["model"]
            if dev_info.get("serial"):
                self.serial_number = dev_info["serial"]
            if dev_info.get("battery") is not None:
                self.battery_percent = dev_info["battery"]

            self.status = "CONNECTING"
            self.preset_tables_rx.clear()
            # Critical: Stop BLE scanning before initiating LE connection so BCM4343A2 radio doesn't drop packets!
            self.stop_scan()
            time.sleep(0.15)

            max_attempts = 1 if is_auto else 3
            for attempt in range(1, max_attempts + 1):
                if self.user_disconnected:
                    break
                self.add_log("INFO", f"Connecting to {self.device_name} (try {attempt}/{max_attempts})...")
                try:
                    # If not in BlueZ cache yet, run a brief 1.8s LE scan first
                    objs = self._get_managed_objects()
                    if path not in objs:
                        try:
                            self.bus.call_sync(
                                "org.bluez",
                                "/org/bluez/hci0",
                                "org.bluez.Adapter1",
                                "StartDiscovery",
                                None,
                                None,
                                Gio.DBusCallFlags.NONE,
                                1500,
                                None,
                            )
                            time.sleep(1.8)
                            self.stop_scan()
                            time.sleep(0.15)
                        except Exception:
                            pass

                    # Set Trusted=True so BlueZ maintains link cleanly
                    try:
                        self.bus.call_sync(
                            "org.bluez",
                            path,
                            "org.freedesktop.DBus.Properties",
                            "Set",
                            GLib.Variant("(ssv)", ("org.bluez.Device1", "Trusted", GLib.Variant("b", True))),
                            None,
                            Gio.DBusCallFlags.NONE,
                            1000,
                            None,
                        )
                    except Exception:
                        pass

                    self.bus.call_sync(
                        "org.bluez",
                        path,
                        "org.bluez.Device1",
                        "Connect",
                        None,
                        None,
                        Gio.DBusCallFlags.NONE,
                        10000,
                        None,
                    )

                    # Wait for GATT ServicesResolved
                    for _ in range(32):
                        objs = self._get_managed_objects()
                        d_props = objs.get(path, {}).get("org.bluez.Device1", {})
                        if d_props.get("ServicesResolved", False):
                            break
                        time.sleep(0.2)

                    objs = self._get_managed_objects()
                    self.write_char_path = None
                    self.notify_char_path = None
                    dis_chars = {}

                    for obj_path, ifaces in objs.items():
                        if not obj_path.startswith(path + "/"):
                            continue
                        ch = ifaces.get("org.bluez.GattCharacteristic1")
                        if not ch:
                            continue
                        uuid = ch.get("UUID", "").lower()
                        if uuid == CARTA_WRITE_UUID:
                            self.write_char_path = obj_path
                        elif uuid == CARTA_NOTIFY_UUID:
                            self.notify_char_path = obj_path
                        elif uuid in (DIS_MODEL_UUID, DIS_SERIAL_UUID, DIS_FW_UUID):
                            dis_chars[uuid] = obj_path

                    if not self.write_char_path or not self.notify_char_path:
                        self.add_log("INFO", "Carta GATT characteristics not ready, retrying...")
                        time.sleep(0.6)
                        continue

                    # Start notifications on 0x001b
                    try:
                        self.bus.call_sync(
                            "org.bluez",
                            self.notify_char_path,
                            "org.bluez.GattCharacteristic1",
                            "StartNotify",
                            None,
                            None,
                            Gio.DBusCallFlags.NONE,
                            4000,
                            None,
                        )
                    except Exception as ne:
                        if "Already notifying" not in str(ne):
                            raise

                    # Read DIS characteristics if available
                    for uuid, cpath in dis_chars.items():
                        try:
                            res = self.bus.call_sync(
                                "org.bluez",
                                cpath,
                                "org.bluez.GattCharacteristic1",
                                "ReadValue",
                                GLib.Variant("(a{sv})", ({},)),
                                None,
                                Gio.DBusCallFlags.NONE,
                                1500,
                                None,
                            )
                            val_bytes = bytes(res.unpack()[0])
                            txt = val_bytes.decode("utf-8", errors="ignore").replace("\x00", "").strip()
                            if txt:
                                if uuid == DIS_MODEL_UUID:
                                    self.model_number = txt
                                elif uuid == DIS_SERIAL_UUID:
                                    self.serial_number = txt
                                elif uuid == DIS_FW_UUID:
                                    self.firmware_version = txt
                        except Exception:
                            pass

                    self.last_rx_at = time.time()
                    self.last_connected_at = self.last_rx_at
                    self.disconnect_at = 0.0
                    self.reconnect_attempts = 0
                    self.next_reconnect_at = 0.0
                    self._save_device(dev_info, last_connected_at=self.last_connected_at, clean_exit=False)
                    self.status = "CONNECTED"
                    self.add_log("INFO", "Connected! Sending 0xdd UTC sync...")
                    if self.on_connected_cb:
                        self.on_connected_cb()
                    time.sleep(0.15)
                    self.send_time_sync()
                    return
                except Exception as e:
                    self.add_log("INFO", f"Attempt {attempt} failed: {e}")
                    time.sleep(0.8)

            self.status = "DISCONNECTED"
        finally:
            self._connect_lock.release()

    def disconnect(self, user_requested: bool = True) -> None:
        if user_requested:
            self.user_disconnected = True
        with self.lock:
            self.write_queue.clear()
        if self.bus and self.device_path:
            try:
                if self.notify_char_path:
                    self.bus.call_sync(
                        "org.bluez",
                        self.notify_char_path,
                        "org.bluez.GattCharacteristic1",
                        "StopNotify",
                        None,
                        None,
                        Gio.DBusCallFlags.NONE,
                        1500,
                        None,
                    )
            except Exception:
                pass
            try:
                self.bus.call_sync(
                    "org.bluez",
                    self.device_path,
                    "org.bluez.Device1",
                    "Disconnect",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    2500,
                    None,
                )
            except Exception:
                pass
        self.status = "DISCONNECTED"
        self.remaining_sec = 0

    def write_packet(self, pkt: bytes, label: str = "") -> None:
        self.add_log("TX", f"{to_hex(pkt)}" + (f" // {label}" if label else ""))
        if not self.is_connected or not self.bus or not self.write_char_path:
            return
        with self.lock:
            # Coalesce rapid live preview adjustments (0xcc with action 0x00) so slider scrubbing never floods BLE
            if len(pkt) == 16 and pkt[0] == 0xCC and pkt[13] == 0x00 and self.write_queue:
                last_pkt, _ = self.write_queue[-1]
                if len(last_pkt) == 16 and last_pkt[0] == 0xCC and last_pkt[13] == 0x00:
                    self.write_queue[-1] = (pkt, label)
                    self.write_event.set()
                    return
            self.write_queue.append((pkt, label))
        self.write_event.set()

    # High-level commands
    def send_time_sync(self) -> None:
        self.write_packet(pkt_time_sync_utc(), "Time Sync UTC (0xdd)")

    def send_11_settings(
        self,
        unit_byte: int | None = None,
        brightness: int | None = None,
        heat_preset: int | None = None,
        led_preset: int | None = None,
        vibe_level: int | None = None,
        low_power: bool | None = None,
        power_byte: int = 0x00,
    ) -> None:
        if unit_byte is not None:
            self.unit_byte = unit_byte
        if brightness is not None:
            self.led_brightness = brightness
        if heat_preset is not None:
            self.active_heat_preset = max(1, min(5, heat_preset))
        if led_preset is not None:
            self.active_led_preset = max(0, min(5, led_preset))
        if vibe_level is not None:
            self.vibe_level = max(2, min(10, vibe_level))
        if low_power is not None:
            self.low_power_mode = low_power

        pkt = pkt_settings_11(
            self.unit_byte,
            self.led_brightness,
            self.active_heat_preset,
            self.active_led_preset,
            self.vibe_level,
            self.low_power_mode,
            power_byte,
        )
        lbl = "POWER OFF" if power_byte == 0xAF else f"Settings P{self.active_heat_preset} LED={self.active_led_preset}"
        self.write_packet(pkt, lbl)

    def select_heat_preset(self, slot: int) -> None:
        s = max(1, min(5, slot))
        self.active_heat_preset = s
        self.is_manual_heat = False
        tbl = self.presets_f if self.is_fahrenheit else self.presets_c
        if s in tbl:
            self.wax_temp, self.wax_timer_sec = tbl[s]
        htbl = self.herb_presets_f if self.is_fahrenheit else self.herb_presets_c
        if s in htbl:
            self.herb_temp, self.herb_timer_sec = htbl[s]
        self.send_11_settings(heat_preset=s)

    def toggle_unit(self) -> None:
        new_u = 0x22 if self.is_fahrenheit else 0x11
        if new_u == 0x11 and self.unit_byte == 0x22:
            self.wax_temp = c_to_f(self.wax_temp)
            self.current_temp = c_to_f(self.current_temp)
        elif new_u == 0x22 and self.unit_byte == 0x11:
            self.wax_temp = f_to_c(self.wax_temp)
            self.current_temp = f_to_c(self.current_temp)
        self.send_11_settings(unit_byte=new_u)

    def toggle_low_power(self) -> None:
        lp = not self.low_power_mode
        br = 0x02 if lp else 0x08
        self.send_11_settings(low_power=lp, brightness=br)

    def set_vibe_step(self, step_1_to_5: int) -> None:
        lvl = max(1, min(5, step_1_to_5)) * 2
        self.send_11_settings(vibe_level=lvl)

    def set_led_slot(self, slot_0_to_5: int) -> None:
        self.send_11_settings(led_preset=max(0, min(5, slot_0_to_5)))

    def power_off(self) -> None:
        self.send_11_settings(power_byte=0xAF)

    def send_cc(
        self,
        action_byte: int,
        preset_slot: int | None = None,
        wax_temp: int | None = None,
        wax_timer: int | None = None,
        herb_temp: int | None = None,
        herb_timer: int | None = None,
    ) -> None:
        if action_byte == 0xA5 and self.is_connected and not self.has_atomizer:
            self.add_log("INFO", "Blocked 0xA5 START SESH: no atomizer")
            return

        slot = self.active_heat_preset if preset_slot is None else preset_slot
        wt = self.wax_temp if wax_temp is None else wax_temp
        ws = self.wax_timer_sec if wax_timer is None else wax_timer
        ht = self.herb_temp if herb_temp is None else herb_temp
        hs = self.herb_timer_sec if herb_timer is None else herb_timer

        if action_byte == 0x00 and slot in (1, 2, 3, 4, 5):
            self.preset_tables_rx.update((0x22, 0x33, 0x44, 0x55))
            if self.is_fahrenheit:
                self.presets_f[slot] = (wt, ws)
                self.presets_c[slot] = (f_to_c(wt), ws)
                self.herb_presets_f[slot] = (ht, hs)
                self.herb_presets_c[slot] = (f_to_c(ht), hs)
                tbl_66 = self.presets_f
            else:
                self.presets_c[slot] = (wt, ws)
                self.presets_f[slot] = (c_to_f(wt), ws)
                self.herb_presets_c[slot] = (ht, hs)
                self.herb_presets_f[slot] = (c_to_f(ht), hs)
                tbl_66 = self.presets_c
            if slot == self.active_heat_preset:
                self.wax_temp = wt
                self.wax_timer_sec = ws
                self.herb_temp = ht
                self.herb_timer_sec = hs
                self.is_manual_heat = False
            pkt66 = pkt_preset_table_66(tbl_66, self.unit_byte)
            self.write_packet(pkt66, f"SAVE TABLE 0x66 P{slot}={wt}°/{ws}s")
            if self.last_known_dev:
                self._save_device(self.last_known_dev, clean_exit=False)
        else:
            if action_byte == 0x00 and slot == 0:
                self.is_manual_heat = True
            self.wax_temp = wt
            self.wax_timer_sec = ws
            self.herb_temp = ht
            self.herb_timer_sec = hs

        pkt = pkt_cc_command(
            ht,
            wt,
            self.unit_byte,
            hs,
            ws,
            slot,
            action_byte,
        )
        lbl = "START SESH" if action_byte == 0xA5 else ("STOP SESH" if action_byte == 0xAF else f"CC {wt}°/{ws}s")
        self.write_packet(pkt, lbl)

    def send_timeouts(self, led_min: int, sleep_min: int) -> None:
        self.led_timeout_sec = max(1, min(15, led_min)) * 60
        self.sleep_timeout_sec = max(1, min(15, sleep_min)) * 60
        self.write_packet(
            pkt_timeouts_d1(self.led_timeout_sec, self.sleep_timeout_sec),
            f"Timeouts LED={led_min}m Sleep={sleep_min}m",
        )

    def send_rename(self, new_name: str) -> None:
        clean = new_name.strip()[:29]
        if not clean:
            return
        self.device_name = clean
        p1, p2 = pkt_rename(clean)
        self.write_packet(p1, f'Rename 1 "{clean}"')
        threading.Timer(0.18, lambda: self.write_packet(p2, "Rename 2")).start()

    def send_led_preset_config(self, slot: int, mode_byte: int, colors: list[int]) -> None:
        s = max(1, min(5, slot))
        self.led_presets[s] = {"mode": mode_byte, "colors": list(colors)}
        self.send_11_settings(led_preset=s)
        pkt = pkt_led_config(s, mode_byte, colors)
        threading.Timer(0.15, lambda: self.write_packet(pkt, f"LED Slot {s} Config")).start()

    def _handle_notification(self, b: bytes) -> None:
        if not b:
            return
        self.last_rx_at = time.time()
        op = b[0]
        if op == 0x99 and len(b) == 20:
            atomizer = (b[2] & 0x40) != 0
            u = b[3]
            raw_preset = b[4] & 0x0F
            rem_sec = b[5]
            cur_temp = (b[6] << 8) | b[7]
            herb_temp = (b[8] << 8) | b[9]
            wax_temp = (b[10] << 8) | b[11]
            bat = b[12]
            led_preset = (b[13] >> 4) & 0x0F
            led_bright = b[13] & 0x0F
            herb_timer = b[14]
            wax_timer = b[15]
            charging = b[16] != 0
            vibe = (b[17] >> 4) & 0x0F
            lp = (b[17] & 0x0F) != 0
            standby = b[18]

            key = f"{b[2]}-{u}-{raw_preset}-{rem_sec}-{wax_temp}-{bat}-{b[13]}-{b[16]}-{b[17]}"
            if not self.hide_spam_logs or key != self.last_99_key:
                self.add_log("RX", f"{to_hex(b)} // 0x99")
                self.last_99_key = key

            self.has_atomizer = atomizer
            self.unit_byte = u
            is_manual = raw_preset == 0
            self.is_manual_heat = is_manual
            if 1 <= raw_preset <= 5:
                self.active_heat_preset = raw_preset
            self.remaining_sec = rem_sec
            self.current_temp = cur_temp

            if not is_manual and 1 <= raw_preset <= 5:
                w_op = 0x33 if u == 0x11 else 0x22
                h_op = 0x55 if u == 0x11 else 0x44
                wtbl = self.presets_f if u == 0x11 else self.presets_c
                htbl = self.herb_presets_f if u == 0x11 else self.herb_presets_c
                ap = wtbl.get(raw_preset) if w_op in self.preset_tables_rx else None
                hp = htbl.get(raw_preset) if h_op in self.preset_tables_rx else None
                self.wax_temp = ap[0] if ap else wax_temp
                self.wax_timer_sec = ap[1] if ap else wax_timer
                self.herb_temp = hp[0] if hp else herb_temp
                self.herb_timer_sec = hp[1] if hp else herb_timer
            else:
                self.herb_temp = herb_temp
                self.wax_temp = wax_temp
                self.herb_timer_sec = herb_timer
                self.wax_timer_sec = wax_timer

            self.battery_percent = bat
            self.is_charging = charging
            self.active_led_preset = led_preset
            if led_bright > 0:
                self.led_brightness = led_bright
            if vibe > 0:
                self.vibe_level = vibe
            self.low_power_mode = lp
            self.standby_countdown = standby

            if self.on_telemetry_cb:
                self.on_telemetry_cb(cur_temp, self.wax_temp, rem_sec, u == 0x11)

        elif op == 0xAA and len(b) == 19:
            c1, c2, c3, c4 = struct.unpack(">IIII", b[2:18])
            self.dab_counter_1 = c1
            self.dab_counter_2 = c2
            self.dab_counter_3 = c3
            self.dab_counter_4 = c4
            self.add_log("RX", f"Dabs: {c1} / {c2} / {c3} / {c4}")

        elif op in (0x22, 0x33, 0x44, 0x55) and len(b) == 18:
            tbl = {}
            for i in range(5):
                off = 2 + i * 3
                t = (b[off] << 8) | b[off + 1]
                sec = b[off + 2]
                tbl[i + 1] = (t, sec)
            self.preset_tables_rx.add(op)
            if op == 0x22:
                self.presets_c = tbl
                if not self.is_manual_heat and not self.is_fahrenheit and self.active_heat_preset in tbl:
                    self.wax_temp, self.wax_timer_sec = tbl[self.active_heat_preset]
            elif op == 0x33:
                self.presets_f = tbl
                if not self.is_manual_heat and self.is_fahrenheit and self.active_heat_preset in tbl:
                    self.wax_temp, self.wax_timer_sec = tbl[self.active_heat_preset]
            elif op == 0x44:
                self.herb_presets_c = tbl
                if not self.is_manual_heat and not self.is_fahrenheit and self.active_heat_preset in tbl:
                    self.herb_temp, self.herb_timer_sec = tbl[self.active_heat_preset]
            elif op == 0x55:
                self.herb_presets_f = tbl
                if not self.is_manual_heat and self.is_fahrenheit and self.active_heat_preset in tbl:
                    self.herb_temp, self.herb_timer_sec = tbl[self.active_heat_preset]
            self.add_log("RX", f"Preset Table 0x{op:02x}")

        elif 0xE6 <= op <= 0xEA and len(b) == 20:
            slot = 0xEA - op + 1
            mode = b[3]
            cols = []
            for i in range(5):
                off = 4 + i * 3
                cols.append((b[off] << 16) | (b[off + 1] << 8) | b[off + 2])
            self.led_presets[slot] = {"mode": mode, "colors": cols}
            self.add_log("RX", f"LED Slot {slot} Table")

        elif op == 0xD2 and len(b) == 7:
            self.led_timeout_sec = (b[2] << 8) | b[3]
            self.sleep_timeout_sec = (b[4] << 8) | b[5]
            self.add_log("RX", f"Timeouts: LED={self.led_timeout_sec}s Sleep={self.sleep_timeout_sec}s")


# ==============================================================================
# MAIN OPENCARTAZERO APPLICATION
# ==============================================================================
class OpenCartaZeroApp:
    TABS = ["CONNECT", "HOME", "CURVES", "DEVICE"]

    def __init__(self, preview_out: str | None = None, preview_tab: str | None = None) -> None:
        self.preview_out = preview_out
        self.preview_tab = preview_tab

        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.Surface((W, H), 0, 16, (0xF800, 0x07E0, 0x001F, 0))

        self.fb_fd = None
        if not self.preview_out:
            for fb_path in ("/dev/fb0", "/dev/fb1"):
                try:
                    self.fb_fd = os.open(fb_path, os.O_RDWR)
                    break
                except Exception:
                    pass

        self.kbd_fds = []
        if not self.preview_out:
            kbd_paths = [KBD_DEV] if os.path.exists(KBD_DEV) else ["/dev/input/event0", "/dev/input/event1", "/dev/input/event2"]
            for p in kbd_paths:
                if os.path.exists(p):
                    try:
                        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
                        self.kbd_fds.append(fd)
                    except Exception:
                        pass

        def _f(path: str, sz: int, bold: bool = False):
            try:
                return pygame.font.Font(path, sz)
            except Exception:
                return pygame.font.SysFont("dejavusans", sz, bold=bold)

        self.f_xs = _f(FONT_REG, 9)
        self.f_xs_b = _f(FONT_BOLD, 9, True)
        self.f_sm = _f(FONT_REG, 10)
        self.f_sm_b = _f(FONT_BOLD, 10, True)
        self.f_md = _f(FONT_BOLD, 12, True)
        self.f_lg = _f(FONT_BOLD, 15, True)
        self.f_xl = _f(FONT_BOLD, 20, True)
        self.f_mono = _f(FONT_MONO, 9)

        self.running = True
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))

        self.ble = CartaBleManager()
        self.ble.on_telemetry_cb = self._on_telemetry
        self.ble.on_connected_cb = self._on_ble_connected

        # Navigation & Focus State
        self.tab_idx = 0  # 0=CONNECT, 1=HOME, 2=CURVES, 3=DEVICE
        self.modal: str | None = None  # None, "SESH_PRESET", "LED_EDITOR", "CURVE_EDIT", "CURVE_GEN", "BLE_LOG", "RENAME", "POWER_OFF"

        # Connect Screen State
        self.conn_sel = 0
        self.conn_focus = 0  # 0=Device/Scan, 1=ShowAllBLE, 2=OfflineMode

        # Home Screen Focus (0=SeshPreset, 1=LedPreset, 2=TempSlider, 3=DurSlider, 4=Start/Stop CTA)
        self.home_focus = 2

        # Sesh Preset Editor Modal State
        self.sp_slot = 1
        self.sp_herb = False
        self.sp_focus = 1  # 0=Slot, 1=Temp, 2=Dur, 3=Save
        self.sp_wax_temp = 230
        self.sp_wax_timer = 55
        self.sp_herb_temp = 165
        self.sp_herb_timer = 120

        # LED Editor Modal State
        self.le_slot = 5
        self.le_focus = 2  # 0=Slot, 1=AnimMode, 2=Stop1..5, 3=ColorPalette, 4=Save
        self.le_stop_idx = 0

        # Curves State
        self.curve_idx = 0
        self.curves = self._load_curves()
        self.curve_focus = 0  # 0=Preset, 1=Mode(Smooth/Step), 2=EditPts, 3=AutoGen, 4=Run/Stop
        self.ce_pt_idx = 0
        self.ce_field = 0  # 0=Time, 1=Temp
        self.cg_start = 245
        self.cg_end = 215
        self.cg_dur = 55
        self.cg_shape_idx = 0
        self.cg_focus = 0  # 0=Start, 1=End, 2=Dur, 3=Shape, 4=Generate

        # Curve Runner State
        self.curve_running = False
        self.curve_phase = "IDLE"  # IDLE, PREHEAT, ACTIVE
        self.curve_elapsed = 0
        self.curve_last_sent = None
        self.curve_trace: list[tuple[int, int]] = []
        self.sim_last_tick = time.time()

        # Device Settings Focus (0=LowPower, 1=Unit, 2=Vibe, 3=SleepMin, 4=LedMin, 5=SyncTime, 6=Rename, 7=BleLog, 8=PowerOff)
        self.dev_focus = 0
        self.rename_buf = ""
        self.rename_target = "DEVICE"  # "DEVICE" or "CURVE"
        self.log_scroll = 0

        # Toast, Shift & ESC Hold
        self.toast_msg = ""
        self.toast_until = 0.0
        self.esc_down_at: float | None = None
        self.shift_down = False
        self.shift_latch = False
        self.shift_used = False

        if not self.preview_out:
            recent = (time.time() - self.ble.last_connected_at) <= 120.0
            if self.ble.last_known_dev and not self.ble.was_clean_exit and recent:
                self.ble.scanned_devices = [self.ble.last_known_dev]
                self.ble.disconnect_at = time.time()
                self.ble.connect_device(self.ble.last_known_dev, is_auto=True)
                self.show_toast("Recovering recent session...")
            else:
                self.ble.user_disconnected = True
                self.ble.start_scan()

    def _load_curves(self) -> list[dict]:
        defaults = [
            {
                "id": c["id"],
                "name": c["name"],
                "mode": c["mode"],
                "desc": c["desc"],
                "pointsC": [list(p) for p in c["pointsC"]],
                "custom": False,
            }
            for c in BUILTIN_CURVES
        ]
        try:
            if os.path.exists(CURVES_FILE):
                with open(CURVES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("curves"):
                    loaded = []
                    for c in data["curves"]:
                        loaded.append(
                            {
                                "id": c.get("id", f"custom_{len(loaded)}"),
                                "name": c.get("name", "Custom"),
                                "mode": c.get("mode", "smooth"),
                                "desc": c.get("desc", ""),
                                "pointsC": [list(p) for p in c.get("pointsC", [[0, 220], [50, 235]])],
                                "custom": bool(c.get("custom", False)),
                            }
                        )
                    if loaded:
                        self.curve_idx = max(0, min(len(loaded) - 1, int(data.get("active_idx", 0))))
                        return loaded
                elif isinstance(data, list):
                    for c in data:
                        c["custom"] = True
                        defaults.append(c)
        except Exception:
            pass
        return defaults

    def _save_custom_curves(self) -> None:
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CURVES_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "active_idx": self.curve_idx % max(1, len(self.curves)),
                        "curves": self.curves,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    @property
    def active_curve(self) -> dict:
        return self.curves[self.curve_idx % len(self.curves)]

    def show_toast(self, msg: str, dur: float = 2.0) -> None:
        self.toast_msg = msg
        self.toast_until = time.time() + dur

    def flush_fb(self) -> None:
        if self.fb_fd is not None:
            try:
                os.lseek(self.fb_fd, 0, os.SEEK_SET)
                os.write(self.fb_fd, bytes(self.screen.get_buffer()))
            except Exception:
                pass

    # ==========================================================================
    # TELEMETRY & CURVE RUNNER
    # ==========================================================================
    def _on_ble_connected(self) -> None:
        if self.tab_idx == 0:
            self.tab_idx = 1
        self.show_toast(f"Connected to {self.ble.device_name}!", 2.5)

    def _on_telemetry(self, cur_temp: int, wax_temp: int, rem_sec: int, is_f: bool) -> None:
        dur = max(10, max(p[0] for p in self.active_curve["pointsC"]))
        if self.curve_running:
            if rem_sec == 0 and self.curve_phase == "ACTIVE":
                self.curve_running = False
                self.curve_phase = "IDLE"
                self.ble.send_cc(0xAF, preset_slot=0)
                return
            if rem_sec > 0:
                elapsed = max(0, dur - rem_sec)
                self.curve_phase = "ACTIVE" if elapsed > 0 else "PREHEAT"
                self.curve_elapsed = elapsed
                self.curve_trace.append((elapsed, cur_temp))
                if len(self.curve_trace) > 120:
                    self.curve_trace.pop(0)

                desired_c = eval_curve_temp_c(self.active_curve["pointsC"], self.active_curve["mode"], elapsed)
                desired_u = c_to_f(desired_c) if is_f else desired_c
                if rem_sec > 1 and desired_u != self.curve_last_sent:
                    self.ble.send_cc(0x00, preset_slot=0, wax_temp=desired_u, wax_timer=dur)
                    self.curve_last_sent = desired_u

    def start_curve_session(self) -> None:
        if self.ble.is_connected and not self.ble.has_atomizer:
            self.show_toast("No atomizer detected!")
            return
        c = self.active_curve
        dur = max(10, max(p[0] for p in c["pointsC"]))
        start_c = eval_curve_temp_c(c["pointsC"], c["mode"], 0)
        start_u = c_to_f(start_c) if self.ble.is_fahrenheit else start_c
        self.curve_running = True
        self.curve_phase = "PREHEAT"
        self.curve_elapsed = 0
        self.curve_last_sent = start_u
        self.curve_trace = [(0, self.ble.current_temp)]
        self.ble.send_cc(0xA5, preset_slot=0, wax_temp=start_u, wax_timer=dur)
        if not self.ble.is_connected:
            # Offline preview simulation
            self.ble.remaining_sec = dur
            self.ble.wax_temp = start_u
            self.ble.wax_timer_sec = dur
        self.show_toast(f"Curve Started ({dur}s)")

    def stop_curve_session(self) -> None:
        self.curve_running = False
        self.curve_phase = "IDLE"
        self.ble.send_cc(0xAF, preset_slot=0)
        if not self.ble.is_connected:
            self.ble.remaining_sec = 0
        self.show_toast("Curve Stopped")

    def step_offline_simulation(self) -> None:
        now = time.time()
        if now - self.sim_last_tick < 1.0:
            return
        self.sim_last_tick = now
        if not self.ble.is_connected and self.ble.remaining_sec > 0:
            if self.ble.current_temp < self.ble.wax_temp - 3:
                step = 28 if self.ble.is_fahrenheit else 16
                self.ble.current_temp = min(self.ble.wax_temp, self.ble.current_temp + step)
            else:
                self.ble.remaining_sec = max(0, self.ble.remaining_sec - 1)
                diff = self.ble.wax_temp - self.ble.current_temp
                self.ble.current_temp += max(-4, min(4, diff))
            self._on_telemetry(
                self.ble.current_temp,
                self.ble.wax_temp,
                self.ble.remaining_sec,
                self.ble.is_fahrenheit,
            )

    # ==========================================================================
    # DRAWING PRIMITIVES
    # ==========================================================================
    def draw_carta_rig(self, cx: int, cy: int, scale: float = 1.0) -> None:
        """Draws the signature OpenCarta hourglass rig + glass top + LED glow."""
        s = self.screen
        leds_on = self.ble.active_led_preset > 0
        heating = self.ble.is_session_active
        led_cfg = self.ble.led_presets.get(self.ble.active_led_preset, {"colors": [0x1ED7A6, 0x58A6FF]})
        c1 = DANGER if heating else (rgb_tuple(led_cfg["colors"][0]) if leds_on else (35, 45, 48))
        c2 = WARN if heating else (rgb_tuple(led_cfg["colors"][1]) if leds_on else c1)

        # Ambient aura ring
        if leds_on or heating:
            pulse = 0.7 + 0.3 * math.sin(time.time() * 3.2)
            aura_col = (int(c1[0] * 0.22 * pulse), int(c1[1] * 0.22 * pulse), int(c1[2] * 0.22 * pulse))
            pygame.draw.circle(s, aura_col, (cx, cy), int(34 * scale))

        # Glass top cone
        pts_glass = [
            (int(cx - 8 * scale), int(cy - 42 * scale)),
            (int(cx + 4 * scale), int(cy - 42 * scale)),
            (int(cx + 14 * scale), int(cy - 22 * scale)),
            (int(cx + 12 * scale), int(cy - 2 * scale)),
            (int(cx - 18 * scale), int(cy - 2 * scale)),
            (int(cx - 19 * scale), int(cy - 22 * scale)),
        ]
        pygame.draw.polygon(s, (32, 42, 46), pts_glass)
        pygame.draw.polygon(s, (71, 86, 92), pts_glass, 1)

        # Inner percolator pillar
        pygame.draw.rect(
            s,
            (54, 68, 74),
            (int(cx - 7 * scale), int(cy - 30 * scale), int(10 * scale), int(24 * scale)),
            border_radius=3,
        )

        # Glowing glass collar
        if leds_on or heating:
            pygame.draw.rect(
                s,
                c1,
                (int(cx - 17 * scale), int(cy - 7 * scale), int(29 * scale), int(5 * scale)),
            )

        # Atomizer & carb cap on right shoulder
        pygame.draw.rect(
            s,
            (32, 36, 39),
            (int(cx + 16 * scale), int(cy - 14 * scale), int(13 * scale), int(12 * scale)),
            border_radius=3,
        )
        pygame.draw.rect(
            s,
            DANGER if heating else (52, 58, 63),
            (int(cx + 17 * scale), int(cy - 18 * scale), int(10 * scale), int(4 * scale)),
            border_radius=2,
        )

        # Ergonomic body
        pts_body = [
            (int(cx - 18 * scale), int(cy - 2 * scale)),
            (int(cx + 30 * scale), int(cy - 2 * scale)),
            (int(cx + 28 * scale), int(cy + 8 * scale)),
            (int(cx + 18 * scale), int(cy + 18 * scale)),
            (int(cx + 20 * scale), int(cy + 34 * scale)),
            (int(cx - 20 * scale), int(cy + 34 * scale)),
            (int(cx - 15 * scale), int(cy + 18 * scale)),
            (int(cx - 19 * scale), int(cy + 6 * scale)),
        ]
        pygame.draw.polygon(s, (24, 28, 31), pts_body)
        pygame.draw.polygon(s, (52, 58, 63), pts_body, 1)

        # V emblem
        pygame.draw.lines(
            s,
            SUBTEXT,
            False,
            [
                (int(cx - 7 * scale), int(cy + 4 * scale)),
                (int(cx - 4 * scale), int(cy + 9 * scale)),
                (int(cx - 1 * scale), int(cy + 4 * scale)),
            ],
            1,
        )

        # Base LED ring
        pygame.draw.rect(
            s,
            c2 if (leds_on or heating) else (44, 50, 54),
            (int(cx - 20 * scale), int(cy + 35 * scale), int(40 * scale), int(3 * scale)),
            border_radius=2,
        )
        # Foot
        pygame.draw.rect(
            s,
            (14, 16, 18),
            (int(cx - 19 * scale), int(cy + 38 * scale), int(38 * scale), int(3 * scale)),
            border_radius=2,
        )

    def draw_header(self) -> None:
        s = self.screen
        pygame.draw.rect(s, SURFACE, (0, 0, W, 22))
        pygame.draw.line(s, BORDER, (0, 21), (W, 21), 1)

        # Brand Logo: ӨPENCARTA
        logo = self.f_md.render("ӨPENCARTA", True, TEXT)
        s.blit(logo, (6, 4))

        # 4 Tabs in center
        tx = 88
        for idx, tname in enumerate(self.TABS):
            active = idx == self.tab_idx and self.modal is None
            tw = 39 if tname != "CONNECT" else 48
            rect = (tx, 3, tw, 16)
            if active:
                pygame.draw.rect(s, MINT_DARK, rect, border_radius=4)
                pygame.draw.rect(s, MINT, rect, width=1, border_radius=4)
            lbl = self.f_xs_b.render(tname, True, MINT if active else SUBTEXT)
            s.blit(lbl, (tx + tw // 2 - lbl.get_width() // 2, 5))
            tx += tw + 2

        # Right status: BLE dot + Battery
        dot_col = DANGER if self.ble.is_session_active else (MINT if self.ble.is_connected else WARN)
        pygame.draw.circle(s, dot_col, (W - 43, 11), 3)

        bat_txt = f"{self.ble.battery_percent}%" if self.ble.is_connected else "--%"
        bt_col = MINT if (self.ble.is_connected and self.ble.is_charging) else SUBTEXT
        bt_surf = self.f_xs_b.render(bat_txt, True, bt_col)
        s.blit(bt_surf, (W - 18 - bt_surf.get_width(), 5))

        # Battery icon
        bx, by = W - 15, 6
        b_outline = MINT if (self.ble.is_connected and self.ble.is_charging) else SUBTEXT
        pygame.draw.rect(s, b_outline, (bx, by, 10, 10), width=1, border_radius=2)
        pygame.draw.rect(s, b_outline, (bx + 3, by - 2, 4, 2))
        if self.ble.is_connected:
            fh = max(1, int(6 * self.ble.battery_percent / 100.0))
            bcol = DANGER if self.ble.battery_percent <= 20 else MINT
            pygame.draw.rect(s, bcol, (bx + 2, by + 8 - fh, 6, fh))
            if self.ble.is_charging:
                pygame.draw.lines(
                    s,
                    WARN,
                    False,
                    [(bx + 6, by + 1), (bx + 3, by + 5), (bx + 6, by + 5), (bx + 4, by + 9)],
                    1,
                )

    def draw_footer(self, hint: str) -> None:
        s = self.screen
        pygame.draw.rect(s, SURFACE, (0, H - 15, W, 15))
        pygame.draw.line(s, BORDER, (0, H - 15), (W, H - 15), 1)
        now = time.time()
        if now < self.toast_until and self.toast_msg:
            txt = self.f_xs_b.render(self.toast_msg, True, MINT)
        else:
            txt = self.f_xs.render(hint, True, SUBTEXT)
        s.blit(txt, (6, H - 13))

        if self.esc_down_at is not None:
            elapsed = min(2.0, now - self.esc_down_at)
            pct = elapsed / 2.0
            pygame.draw.rect(s, ELEVATED, (50, 62, 220, 44), border_radius=8)
            pygame.draw.rect(s, DANGER, (50, 62, 220, 44), width=2, border_radius=8)
            lbl = self.f_sm_b.render(f"HOLD ESC TO EXIT... {max(0.0, 2.0 - elapsed):.1f}s", True, TEXT)
            s.blit(lbl, (160 - lbl.get_width() // 2, 70))
            pygame.draw.rect(s, BG, (64, 88, 192, 8), border_radius=4)
            pygame.draw.rect(s, DANGER, (64, 88, int(192 * pct), 8), border_radius=4)

    # ==========================================================================
    # TAB 0: CONNECT SCREEN
    # ==========================================================================
    def draw_connect(self) -> None:
        s = self.screen
        cx, cy = 160, 82

        # Concentric radar stadium rings (matching OpenCarta ConnectScreen.kt)
        pulse = 0.5 + 0.5 * math.sin(time.time() * 2.5)
        for i, (rw, rh) in enumerate([(150, 74), (200, 96), (250, 114), (298, 126)]):
            c_val = int((28 - i * 5) * (0.7 + 0.3 * pulse))
            pygame.draw.rect(
                s,
                (0, c_val + 14, int(c_val * 0.85) + 10),
                (cx - rw // 2, cy - rh // 2, rw, rh),
                width=1,
                border_radius=rh // 2,
            )

        with self.ble.lock:
            devs = list(self.ble.scanned_devices)

        # Central stadium card
        card_rect = (46, 28, 228, 96)
        pygame.draw.rect(s, SURFACE, card_rect, border_radius=48)
        pygame.draw.rect(
            s,
            MINT if self.conn_focus == 0 else BORDER,
            card_rect,
            width=2 if self.conn_focus == 0 else 1,
            border_radius=48,
        )

        if self.ble.status == "CONNECTING":
            t1 = self.f_md.render("Connecting to Carta...", True, MINT)
            t2 = self.f_xs.render(f"{self.ble.device_name} ({self.ble.device_address})", True, SUBTEXT)
            s.blit(t1, (160 - t1.get_width() // 2, 62))
            s.blit(t2, (160 - t2.get_width() // 2, 82))
        elif self.ble.is_connected:
            self.draw_carta_rig(92, 76, scale=0.82)
            t1 = self.f_md.render(self.ble.device_name[:18], True, MINT)
            t2 = self.f_xs.render(f"{self.ble.device_address} • Connected", True, TEXT)
            t3 = self.f_xs.render(f"SN:{self.ble.serial_number}  FW:{self.ble.firmware_version}", True, SUBTEXT)
            s.blit(t1, (124, 42))
            s.blit(t2, (124, 60))
            s.blit(t3, (124, 74))
            btn = (124, 92, 112, 20)
            pygame.draw.rect(s, DANGER, btn, border_radius=10)
            bl = self.f_xs_b.render("DISCONNECT [Enter]", True, TEXT)
            s.blit(bl, (180 - bl.get_width() // 2, 96))
        elif not devs:
            self.draw_carta_rig(92, 76, scale=0.82)
            msg = "Searching for Carta..." if self.ble.status == "SCANNING" else "No Carta found yet"
            t1 = self.f_md.render(msg, True, TEXT)
            t2 = self.f_xs.render("Turn on Carta or press R to rescan", True, SUBTEXT)
            s.blit(t1, (120, 48))
            s.blit(t2, (120, 66))
            btn = (120, 86, 108, 22)
            pygame.draw.rect(s, MINT, btn, border_radius=11)
            bl = self.f_xs_b.render("SCAN NOW [Enter]", True, BG)
            s.blit(bl, (174 - bl.get_width() // 2, 91))
        else:
            self.conn_sel = self.conn_sel % len(devs)
            d = devs[self.conn_sel]
            self.draw_carta_rig(88, 76, scale=0.82)
            t1 = self.f_md.render(d.get("name", "Carta")[:17], True, TEXT)
            bat_s = f" • {d['battery']}%" if d.get("battery") is not None else ""
            rssi_s = f"{d['rssi']}dBm" if d.get("rssi") is not None else "saved"
            t2 = self.f_xs.render(f"{d.get('address', '')} ({rssi_s}{bat_s})", True, SUBTEXT)
            t3 = self.f_xs_b.render(f"Device {self.conn_sel + 1}/{len(devs)} ([ / ] cycle)", True, MINT)
            s.blit(t1, (118, 38))
            s.blit(t2, (118, 55))
            s.blit(t3, (118, 70))

            # Mint circle arrow button + Connect pill
            btn = (118, 86, 116, 24)
            pygame.draw.rect(s, MINT, btn, border_radius=12)
            bl = self.f_sm_b.render("CONNECT ->", True, BG)
            s.blit(bl, (176 - bl.get_width() // 2, 92))

        # Bottom controls row: [x] Show all BLE   |   Continue Offline ->
        chk_rect = (18, 130, 138, 20)
        pygame.draw.rect(s, SURFACE, chk_rect, border_radius=6)
        pygame.draw.rect(
            s,
            MINT if self.conn_focus == 1 else BORDER,
            chk_rect,
            width=1,
            border_radius=6,
        )
        box = (24, 134, 12, 12)
        pygame.draw.rect(s, MINT if self.ble.show_all_ble else ELEVATED, box, border_radius=3)
        if not self.ble.show_all_ble:
            pygame.draw.rect(s, SUBTEXT, box, width=1, border_radius=3)
        clbl = self.f_xs.render("Show all BLE (A)", True, TEXT if self.conn_focus == 1 else SUBTEXT)
        s.blit(clbl, (42, 134))

        off_rect = (164, 130, 138, 20)
        pygame.draw.rect(s, SURFACE, off_rect, border_radius=6)
        pygame.draw.rect(
            s,
            MINT if self.conn_focus == 2 else BORDER,
            off_rect,
            width=1,
            border_radius=6,
        )
        olbl = self.f_xs_b.render("Continue Offline (O) ->", True, MINT)
        s.blit(olbl, (233 - olbl.get_width() // 2, 134))

        self.draw_footer("1-4:Tab  F/X:Focus  [,]:Dev  Enter:Connect  R:Scan  O:Offline")

    # ==========================================================================
    # TAB 1: HOME DASHBOARD (Exact OpenCarta Layout adapted to 320x170)
    # ==========================================================================
    def draw_home(self) -> None:
        s = self.screen
        u = self.ble.unit_str

        # --- LEFT COLUMN (x=6..92): Device Graphic + Idle Bar + Preset Pills ---
        pygame.draw.rect(s, SURFACE, (6, 25, 86, 94), border_radius=8)
        pygame.draw.rect(s, BORDER, (6, 25, 86, 94), width=1, border_radius=8)
        self.draw_carta_rig(46, 65, scale=0.72)

        # Idle countdown bar inside left card bottom
        max_sleep = max(1, self.ble.sleep_timeout_sec)
        idle_sec = min(max_sleep, int(round(self.ble.standby_countdown * 2.5)))
        if self.ble.is_session_active:
            idle_txt = f"SESH {self.ble.remaining_sec}s"
            idle_frac = self.ble.remaining_sec / float(max(1, self.ble.wax_timer_sec))
            bar_col = DANGER
        elif self.ble.standby_countdown > 0:
            idle_txt = f"IDLE {idle_sec // 60}:{idle_sec % 60:02d}"
            idle_frac = idle_sec / float(max_sleep)
            bar_col = MINT_DIM
        else:
            if max_sleep > 600:
                idle_txt = "IDLE 10:00+"
            else:
                idle_txt = f"IDLE {max_sleep // 60}:{max_sleep % 60:02d}"
            idle_frac = 1.0
            bar_col = MUTED

        it_surf = self.f_xs.render(idle_txt, True, SUBTEXT)
        s.blit(it_surf, (49 - it_surf.get_width() // 2, 101))
        pygame.draw.rect(s, ELEVATED, (14, 113, 70, 3), border_radius=2)
        pygame.draw.rect(s, bar_col, (14, 113, int(70 * max(0.0, min(1.0, idle_frac))), 3), border_radius=2)

        # SESH PRESET (focus 0) & LED PRESET (focus 1) pills below graphic
        sp_rect = (6, 122, 41, 29)
        pygame.draw.rect(s, SURFACE, sp_rect, border_radius=6)
        pygame.draw.rect(
            s,
            MINT if self.home_focus == 0 else BLUE,
            sp_rect,
            width=2 if self.home_focus == 0 else 1,
            border_radius=6,
        )
        s.blit(self.f_xs.render("SESH", True, SUBTEXT), (14, 124))
        p_txt = self.f_md.render(f"P{self.ble.active_heat_preset}", True, TEXT)
        s.blit(p_txt, (26 - p_txt.get_width() // 2, 135))

        lp_rect = (51, 122, 41, 29)
        led_cfg = self.ble.led_presets.get(self.ble.active_led_preset, {"colors": [0x1ED7A6]})
        led_c = rgb_tuple(led_cfg["colors"][0]) if self.ble.active_led_preset > 0 else MUTED
        pygame.draw.rect(s, SURFACE, lp_rect, border_radius=6)
        pygame.draw.rect(
            s,
            MINT if self.home_focus == 1 else led_c,
            lp_rect,
            width=2 if self.home_focus == 1 else 1,
            border_radius=6,
        )
        s.blit(self.f_xs.render("LED", True, SUBTEXT), (62, 124))
        l_str = "OFF" if self.ble.active_led_preset == 0 else f"L{self.ble.active_led_preset}"
        l_txt = self.f_md.render(l_str, True, TEXT)
        s.blit(l_txt, (71 - l_txt.get_width() // 2, 135))

        # --- RIGHT COLUMN (x=98..314): Info Row + Live Temp Pill + Sliders + Start CTA ---
        # Row 1: SPORT iNTELLi-CORE + Total Dabs + Status
        s.blit(self.f_md.render("SPORT", True, TEXT), (98, 24))
        s.blit(self.f_xs.render("iNTELLi-CORE", True, SUBTEXT), (148, 27))
        dabs_str = f"DABS: {self.ble.dab_counter_1}"
        ds = self.f_xs_b.render(dabs_str, True, MINT)
        s.blit(ds, (314 - ds.get_width(), 27))

        # Row 2: LIVE TEMP Pill
        lt_rect = (98, 40, 216, 22)
        pygame.draw.rect(s, SURFACE, lt_rect, border_radius=6)
        pygame.draw.rect(s, BORDER, lt_rect, width=1, border_radius=6)
        dot_c = WARN if not self.ble.has_atomizer else (DANGER if self.ble.is_session_active else MINT)
        pygame.draw.circle(s, dot_c, (107, 51), 3)
        s.blit(self.f_xs_b.render("LIVE TEMP", True, SUBTEXT), (114, 45))

        cur_t_str = f"{self.ble.current_temp}{u}" if self.ble.has_atomizer else f"--{u}"
        ct_surf = self.f_md.render(cur_t_str, True, TEXT)
        s.blit(ct_surf, (204 - ct_surf.get_width() // 2, 43))

        phase_str = (
            "NO ATOMIZER"
            if not self.ble.has_atomizer
            else (
                f"PRE-HEAT {self.ble.remaining_sec}s"
                if self.ble.is_preheating
                else (f"ACTIVE {self.ble.remaining_sec}s" if self.ble.is_session_active else "AMBIENT")
            )
        )
        ph_col = WARN if not self.ble.has_atomizer else (DANGER if self.ble.is_session_active else MUTED)
        ph_surf = self.f_xs_b.render(phase_str, True, ph_col)
        s.blit(ph_surf, (308 - ph_surf.get_width(), 45))

        # Row 3: TEMPERATURE Slider Card (focus 2)
        min_t = 300 if self.ble.is_fahrenheit else 150
        max_t = 650 if self.ble.is_fahrenheit else 340
        self._draw_slider_card(
            x=98,
            y=65,
            w=216,
            h=28,
            label="TEMPERATURE",
            val_str=f"{self.ble.wax_temp}{u}",
            frac=(self.ble.wax_temp - min_t) / float(max(1, max_t - min_t)),
            focused=(self.home_focus == 2),
        )

        # Row 4: DURATION Slider Card (focus 3)
        wt = self.ble.wax_timer_sec
        self._draw_slider_card(
            x=98,
            y=96,
            w=216,
            h=28,
            label="DURATION",
            val_str=f"{wt // 60}:{wt % 60:02d} ({wt}s)",
            frac=(wt - 10) / 110.0,
            focused=(self.home_focus == 3),
        )

        # Row 5: Primary CTA Button (TAP TO WARM UP / STOP SESSION) (focus 4)
        cta_rect = (98, 127, 216, 24)
        no_atty = self.ble.is_connected and not self.ble.has_atomizer
        cta_bg = DANGER if self.ble.is_session_active else (ELEVATED if no_atty else MINT)
        cta_fg = TEXT if self.ble.is_session_active else (MUTED if no_atty else BG)
        pygame.draw.rect(s, cta_bg, cta_rect, border_radius=7)
        if self.home_focus == 4:
            pygame.draw.rect(s, TEXT, cta_rect, width=2, border_radius=7)
        cta_txt = (
            f"■ STOP SESSION ({self.ble.remaining_sec}s)"
            if self.ble.is_session_active
            else ("NO ATOMIZER" if no_atty else "▶ TAP TO WARM UP [Space]")
        )
        cs = self.f_sm_b.render(cta_txt, True, cta_fg)
        s.blit(cs, (206 - cs.get_width() // 2, 132))

        self.draw_footer("F/X:Focus  [,]:Adjust  P:Preset  L:LED  Space/Enter:Start/Stop")

    def _draw_slider_card(
        self, x: int, y: int, w: int, h: int, label: str, val_str: str, frac: float, focused: bool
    ) -> None:
        s = self.screen
        rect = (x, y, w, h)
        pygame.draw.rect(s, SURFACE, rect, border_radius=6)
        pygame.draw.rect(s, MINT if focused else BORDER, rect, width=1, border_radius=6)

        s.blit(self.f_xs_b.render(label, True, MINT if focused else SUBTEXT), (x + 6, y + 3))
        vs = self.f_sm_b.render(f"-  {val_str}  +", True, TEXT)
        s.blit(vs, (x + w - 6 - vs.get_width(), y + 2))

        # Track
        tx, ty, tw = x + 8, y + 20, w - 16
        pygame.draw.rect(s, ELEVATED, (tx, ty, tw, 4), border_radius=2)
        fw = int(tw * max(0.0, min(1.0, frac)))
        if fw > 0:
            pygame.draw.rect(s, MINT, (tx, ty, fw, 4), border_radius=2)
        # Thumb circle
        cx = tx + fw
        pygame.draw.circle(s, BG, (cx, ty + 2), 5)
        pygame.draw.circle(s, MINT, (cx, ty + 2), 5, width=2)

    # ==========================================================================
    # TAB 2: TEMPERATURE CURVE STUDIO
    # ==========================================================================
    def draw_curves(self) -> None:
        s = self.screen
        c = self.active_curve
        u = self.ble.unit_str
        is_f = self.ble.is_fahrenheit

        # Top Selector Row (y=24..43)
        sel_rect = (6, 24, 198, 19)
        pygame.draw.rect(s, SURFACE, sel_rect, border_radius=5)
        pygame.draw.rect(
            s,
            MINT if self.curve_focus == 0 else BORDER,
            sel_rect,
            width=1,
            border_radius=5,
        )
        s.blit(self.f_xs_b.render(f"< {c['name'][:26]} >", True, TEXT), (11, 28))

        # Mode toggle (Smooth / Step)
        m_rect = (208, 24, 54, 19)
        pygame.draw.rect(s, SURFACE, m_rect, border_radius=5)
        pygame.draw.rect(
            s,
            MINT if self.curve_focus == 1 else BORDER,
            m_rect,
            width=1,
            border_radius=5,
        )
        m_lbl = "SMOOTH" if c["mode"] == "smooth" else "STEP"
        ms = self.f_xs_b.render(m_lbl, True, MINT)
        s.blit(ms, (235 - ms.get_width() // 2, 28))

        # Status badge
        b_rect = (266, 24, 48, 19)
        b_col = DANGER if self.curve_phase == "PREHEAT" else (MINT if self.curve_running else MUTED)
        pygame.draw.rect(s, SURFACE, b_rect, border_radius=5)
        pygame.draw.rect(s, b_col, b_rect, width=1, border_radius=5)
        b_txt = f"{self.curve_elapsed}s" if self.curve_running else "IDLE"
        bs = self.f_xs_b.render(b_txt, True, b_col)
        s.blit(bs, (290 - bs.get_width() // 2, 28))

        # Interactive Graph Box (y=46..126)
        gx, gy, gw, gh = 6, 46, 308, 80
        pygame.draw.rect(s, SURFACE, (gx, gy, gw, gh), border_radius=6)
        pygame.draw.rect(s, BORDER, (gx, gy, gw, gh), width=1, border_radius=6)

        pad_l, pad_r, pad_t, pad_b = 28, 8, 8, 13
        pw = gw - pad_l - pad_r
        ph = gh - pad_t - pad_b
        dur = float(max(10, max(p[0] for p in c["pointsC"])))
        pts_u = [c_to_f(p[1]) if is_f else p[1] for p in c["pointsC"]]
        base_min = 390.0 if is_f else 200.0
        base_max = 500.0 if is_f else 260.0
        min_t = float(min(base_min, min(pts_u) - 10))
        max_t = float(max(base_max, max(pts_u) + 10))

        def x_of(t_sec: float) -> int:
            return int(gx + pad_l + (max(0.0, min(dur, t_sec)) / dur) * pw)

        def y_of(temp_u: float) -> int:
            frac = (max(min_t, min(max_t, temp_u)) - min_t) / (max_t - min_t)
            return int(gy + pad_t + ph - frac * ph)

        # Grid lines + Y labels
        for i in range(3):
            tv = min_t + (i / 2.0) * (max_t - min_t)
            yy = y_of(tv)
            pygame.draw.line(s, BORDER, (gx + pad_l, yy), (gx + gw - pad_r, yy), 1)
            yl = self.f_xs.render(f"{int(round(tv))}°", True, MUTED)
            s.blit(yl, (gx + 3, yy - 5))

        # X axis time labels
        for t_tick in (0, int(dur // 2), int(dur)):
            xx = x_of(t_tick)
            xl = self.f_xs.render(f"{t_tick}s", True, MUTED)
            s.blit(xl, (xx - xl.get_width() // 2, gy + gh - 11))

        # Target curve polyline (exact vertex & step-corner geometry so dots sit directly on corners)
        s_pts = sorted(c["pointsC"], key=lambda x: x[0])
        curve_pts = []
        if c["mode"] == "step":
            for i, (pt_t, pt_c) in enumerate(s_pts):
                tu = c_to_f(pt_c) if is_f else pt_c
                px, py = x_of(pt_t), y_of(tu)
                curve_pts.append((px, py))
                if i + 1 < len(s_pts):
                    next_t = s_pts[i + 1][0]
                    curve_pts.append((x_of(next_t), py))
            if s_pts and s_pts[-1][0] < dur:
                last_u = c_to_f(s_pts[-1][1]) if is_f else s_pts[-1][1]
                curve_pts.append((x_of(dur), y_of(last_u)))
        else:
            for pt_t, pt_c in s_pts:
                tu = c_to_f(pt_c) if is_f else pt_c
                curve_pts.append((x_of(pt_t), y_of(tu)))
        if len(curve_pts) >= 2:
            pygame.draw.lines(s, BLUE, False, curve_pts, 2)

        # Live trace (solid red)
        if len(self.curve_trace) >= 2:
            tr_pts = [(x_of(t), y_of(tp)) for t, tp in self.curve_trace]
            pygame.draw.lines(s, DANGER, False, tr_pts, 2)

        # Playhead
        if self.curve_running:
            px = x_of(self.curve_elapsed)
            pygame.draw.line(s, MINT, (px, gy + pad_t), (px, gy + gh - pad_b), 1)

        # Breakpoint dots & labels
        for idx, (pt_t, pt_c) in enumerate(c["pointsC"]):
            tu = c_to_f(pt_c) if is_f else pt_c
            px, py = x_of(pt_t), y_of(tu)
            pygame.draw.circle(s, MINT if idx == self.ce_pt_idx else BLUE, (px, py), 4)
            lbl = self.f_xs_b.render(f"{tu}°", True, TEXT)
            ly = py - 12 if py > gy + 18 else py + 5
            lx = max(gx + pad_l, min(gx + gw - pad_r - lbl.get_width(), px - lbl.get_width() // 2))
            s.blit(lbl, (lx, ly))

        # Bottom Action Buttons Row (y=129..151)
        btns = [
            (6, 129, 94, 22, "EDIT PTS (E)", self.curve_focus == 2, False),
            (104, 129, 94, 22, "AUTO-GEN (G)", self.curve_focus == 3, False),
            (
                202,
                129,
                112,
                22,
                "■ STOP [Space]" if self.curve_running else "▶ RUN CURVE",
                self.curve_focus == 4,
                True,
            ),
        ]
        no_atty = self.ble.is_connected and not self.ble.has_atomizer
        for bx, by, bw, bh, btxt, foc, is_cta in btns:
            if is_cta:
                bg = DANGER if self.curve_running else (ELEVATED if no_atty else MINT)
                fg = TEXT if self.curve_running else (MUTED if no_atty else BG)
            else:
                bg = SURFACE
                fg = TEXT
            pygame.draw.rect(s, bg, (bx, by, bw, bh), border_radius=5)
            if not is_cta:
                pygame.draw.rect(s, MINT if foc else BORDER, (bx, by, bw, bh), width=1, border_radius=5)
            elif foc:
                pygame.draw.rect(s, TEXT, (bx, by, bw, bh), width=2, border_radius=5)
            ts = self.f_xs_b.render(btxt, True, fg)
            s.blit(ts, (bx + bw // 2 - ts.get_width() // 2, by + 6))

        self.draw_footer("[,]:Curve M:Mode E:Pts G:Gen N:New R:Name D:Del Space:Run")

    # ==========================================================================
    # TAB 3: DEVICE SETTINGS (3x3 Grid for 320x170)
    # ==========================================================================
    def draw_device(self) -> None:
        s = self.screen
        vibe_step = max(1, min(5, self.ble.vibe_level // 2))
        sleep_m = max(1, min(15, self.ble.sleep_timeout_sec // 60))
        led_m = max(1, min(15, self.ble.led_timeout_sec // 60))

        # Device Identity Banner (y=24..42)
        pygame.draw.rect(s, SURFACE, (6, 24, 308, 19), border_radius=5)
        pygame.draw.rect(s, BORDER, (6, 24, 308, 19), width=1, border_radius=5)
        id_str = f"{self.ble.device_name.upper()}  •  SN:{self.ble.serial_number}  •  FW:{self.ble.firmware_version}"
        s.blit(self.f_xs_b.render(id_str[:52], True, MINT), (12, 28))

        # 3x3 Settings Grid (y=46..151)
        items = [
            ("LOW POWER", "ON (20%)" if self.ble.low_power_mode else "OFF (80%)", self.ble.low_power_mode),
            ("TEMP UNIT", f"{self.ble.unit_str} (C/F)", True),
            ("VIBE LEVEL", f"< {vibe_step} ({vibe_step * 20}%) >", True),
            ("SLEEP MODE", f"< {sleep_m} min >", False),
            ("LED TIMEOUT", f"< {led_m} min >", False),
            ("SYNC TIME", "0xdd UTC Sync", False),
            ("RENAME", self.ble.device_name[:12], False),
            ("BLE LOG", f"{len(self.ble.logs)} pkts", False),
            ("POWER OFF", "Shutdown 0xaf", False),
        ]

        cw, ch = 100, 32
        for idx, (title, val, hi) in enumerate(items):
            col = idx % 3
            row = idx // 3
            cx = 6 + col * 104
            cy = 46 + row * 35
            foc = idx == self.dev_focus
            is_danger = idx == 8

            pygame.draw.rect(s, SURFACE, (cx, cy, cw, ch), border_radius=6)
            bcol = DANGER if (is_danger and foc) else (MINT if foc else BORDER)
            pygame.draw.rect(s, bcol, (cx, cy, cw, ch), width=2 if foc else 1, border_radius=6)

            t_surf = self.f_xs.render(title, True, DANGER if is_danger else SUBTEXT)
            v_col = DANGER if is_danger else (MINT if hi else TEXT)
            v_surf = self.f_xs_b.render(val, True, v_col)
            s.blit(t_surf, (cx + cw // 2 - t_surf.get_width() // 2, cy + 4))
            s.blit(v_surf, (cx + cw // 2 - v_surf.get_width() // 2, cy + 16))

        self.draw_footer("F/X/Z/C:Select  [,]/Enter:Change  U:Unit  V:Vibe  L:Log")

    # ==========================================================================
    # OVERLAY MODALS (Sesh Preset, LED Editor, Curve Points, Auto-Gen, BLE Log, Rename)
    # ==========================================================================
    def draw_modal(self) -> None:
        s = self.screen
        if self.modal == "SESH_PRESET":
            self._draw_modal_sesh_preset()
        elif self.modal == "LED_EDITOR":
            self._draw_modal_led_editor()
        elif self.modal == "CURVE_EDIT":
            self._draw_modal_curve_edit()
        elif self.modal == "CURVE_GEN":
            self._draw_modal_curve_gen()
        elif self.modal == "BLE_LOG":
            self._draw_modal_ble_log()
        elif self.modal == "RENAME":
            self._draw_modal_rename()
        elif self.modal == "POWER_OFF":
            self._draw_modal_power_off()

    def _draw_modal_box(self, title: str, right_txt: str = "ESC: Back") -> None:
        s = self.screen
        pygame.draw.rect(s, BG, (0, 22, W, H - 37))
        pygame.draw.rect(s, SURFACE, (6, 25, 308, 126), border_radius=8)
        pygame.draw.rect(s, MINT, (6, 25, 308, 126), width=1, border_radius=8)
        s.blit(self.f_md.render(title, True, MINT), (14, 30))
        rt = self.f_xs.render(right_txt, True, SUBTEXT)
        s.blit(rt, (306 - rt.get_width(), 32))
        pygame.draw.line(s, BORDER, (12, 46), (308, 46), 1)

    def _draw_modal_sesh_preset(self) -> None:
        s = self.screen
        u = self.ble.unit_str
        mode_lbl = "HERB" if self.sp_herb else "WAX"
        self._draw_modal_box(f"SESH PRESET #{self.sp_slot} ({mode_lbl})", "M: Wax/Herb  ESC: Back")

        # 5 Preset Pills row
        tbl = (
            (self.ble.herb_presets_f if self.ble.is_fahrenheit else self.ble.herb_presets_c)
            if self.sp_herb
            else (self.ble.presets_f if self.ble.is_fahrenheit else self.ble.presets_c)
        )
        for slot in range(1, 6):
            px = 14 + (slot - 1) * 59
            py = 51
            sel = slot == self.sp_slot
            pt, psec = tbl.get(slot, (230, 55))
            pygame.draw.rect(s, ELEVATED if sel else BG, (px, py, 55, 26), border_radius=5)
            pygame.draw.rect(
                s,
                MINT if sel else BORDER,
                (px, py, 55, 26),
                width=2 if (sel and self.sp_focus == 0) else 1,
                border_radius=5,
            )
            s.blit(self.f_xs_b.render(f"P{slot}: {pt}°", True, MINT if sel else TEXT), (px + 5, py + 3))
            s.blit(self.f_xs.render(f"{psec}s", True, SUBTEXT), (px + 18, py + 14))

        cur_t = self.sp_herb_temp if self.sp_herb else self.sp_wax_temp
        cur_s = self.sp_herb_timer if self.sp_herb else self.sp_wax_timer

        # Temp adjuster
        r1 = (14, 82, 142, 34)
        pygame.draw.rect(s, BG, r1, border_radius=6)
        pygame.draw.rect(s, MINT if self.sp_focus == 1 else BORDER, r1, width=1, border_radius=6)
        s.blit(self.f_xs.render("TEMPERATURE", True, SUBTEXT), (22, 85))
        s.blit(self.f_lg.render(f"< {cur_t}{u} >", True, TEXT), (30, 97))

        # Timer adjuster
        r2 = (164, 82, 142, 34)
        pygame.draw.rect(s, BG, r2, border_radius=6)
        pygame.draw.rect(s, MINT if self.sp_focus == 2 else BORDER, r2, width=1, border_radius=6)
        s.blit(self.f_xs.render("DURATION", True, SUBTEXT), (172, 85))
        s.blit(self.f_lg.render(f"< {cur_s}s >", True, TEXT), (192, 97))

        # Save & Apply button
        btn = (14, 121, 292, 24)
        pygame.draw.rect(s, MINT, btn, border_radius=6)
        if self.sp_focus == 3:
            pygame.draw.rect(s, TEXT, btn, width=2, border_radius=6)
        bt = self.f_sm_b.render(f"SAVE & APPLY TO PRESET #{self.sp_slot} [Enter]", True, BG)
        s.blit(bt, (160 - bt.get_width() // 2, 127))
        self.draw_footer("1-5:Slot  F/X:Field  [,]:Adjust  M:Wax/Herb  Enter:Save")

    def _draw_modal_led_editor(self) -> None:
        s = self.screen
        cfg = self.ble.led_presets.get(self.le_slot, {"mode": 0x13, "colors": [0x1ED7A6] * 5})
        mode_name = next((m[1] for m in LED_MODES if m[0] == cfg["mode"]), "ROTATE")
        self._draw_modal_box(f"LED PRESET #{self.le_slot} — {mode_name}", "0:LED Off  1-5:Slot")

        # Row 1: Slot pills (OFF + L1..L5)
        slots = [0, 1, 2, 3, 4, 5]
        for i, sl in enumerate(slots):
            px = 14 + i * 49
            py = 50
            sel = (sl == 0 and self.ble.active_led_preset == 0) or (sl == self.le_slot and self.ble.active_led_preset > 0)
            pygame.draw.rect(s, ELEVATED if sel else BG, (px, py, 45, 22), border_radius=5)
            pygame.draw.rect(
                s,
                MINT if (sel and self.le_focus == 0) else (MINT_DIM if sel else BORDER),
                (px, py, 45, 22),
                width=1,
                border_radius=5,
            )
            lbl = "OFF" if sl == 0 else f"L{sl}"
            s.blit(self.f_xs_b.render(lbl, True, TEXT), (px + 14, py + 6))

        # Row 2: Animation Mode selector (focus 1)
        am_rect = (14, 76, 292, 20)
        pygame.draw.rect(s, BG, am_rect, border_radius=5)
        pygame.draw.rect(s, MINT if self.le_focus == 1 else BORDER, am_rect, width=1, border_radius=5)
        s.blit(self.f_xs_b.render(f"ANIMATION MODE:   <  {mode_name}  >", True, MINT if self.le_focus == 1 else TEXT), (68, 80))

        # Row 3: 5 RGB Color Stops (focus 2)
        for idx in range(5):
            rgb = cfg["colors"][idx]
            px = 14 + idx * 59
            py = 100
            sel = idx == self.le_stop_idx
            pygame.draw.rect(s, BG, (px, py, 55, 22), border_radius=5)
            pygame.draw.rect(
                s,
                MINT if (sel and self.le_focus == 2) else BORDER,
                (px, py, 55, 22),
                width=2 if (sel and self.le_focus == 2) else 1,
                border_radius=5,
            )
            pygame.draw.circle(s, rgb_tuple(rgb), (px + 10, py + 11), 6)
            s.blit(self.f_xs.render(f"#{idx + 1}", True, TEXT if sel else SUBTEXT), (px + 22, py + 5))

        # Row 4: Save Button (focus 3)
        btn = (14, 125, 292, 21)
        pygame.draw.rect(s, MINT, btn, border_radius=5)
        if self.le_focus == 3:
            pygame.draw.rect(s, TEXT, btn, width=2, border_radius=5)
        bt = self.f_xs_b.render(f"UPLOAD & APPLY LED PRESET #{self.le_slot} [Enter]", True, BG)
        s.blit(bt, (160 - bt.get_width() // 2, 129))
        self.draw_footer("0:Off 1-5:Slot  F/X:Row  Z/C:Stop  [,]:Change Color/Mode  Enter:Save")

    def _draw_modal_curve_edit(self) -> None:
        s = self.screen
        c = self.active_curve
        u = self.ble.unit_str
        is_f = self.ble.is_fahrenheit
        self._draw_modal_box(f"EDIT POINTS: {c['name'][:20]}", "Enter/S:Save  N:Save New")

        pts = c["pointsC"]
        self.ce_pt_idx = self.ce_pt_idx % len(pts)

        # Horizontal list of breakpoints
        for idx, (pt_t, pt_c) in enumerate(pts):
            col = idx % 3
            row = idx // 3
            if row >= 2:
                break
            px = 14 + col * 98
            py = 52 + row * 34
            sel = idx == self.ce_pt_idx
            tu = c_to_f(pt_c) if is_f else pt_c
            pygame.draw.rect(s, ELEVATED if sel else BG, (px, py, 94, 30), border_radius=5)
            pygame.draw.rect(s, MINT if sel else BORDER, (px, py, 94, 30), width=2 if sel else 1, border_radius=5)
            t_col = MINT if (sel and self.ce_field == 0) else TEXT
            c_col = MINT if (sel and self.ce_field == 1) else SUBTEXT
            s.blit(self.f_xs_b.render(f"#{idx + 1}  {pt_t}s", True, t_col), (px + 6, py + 4))
            s.blit(self.f_xs_b.render(f"{tu}{u}", True, c_col), (px + 6, py + 16))

        info = f"Point #{self.ce_pt_idx + 1}: Editing {'TIME (sec)' if self.ce_field == 0 else 'TEMP'}  •  Tab:Switch Time/Temp"
        s.blit(self.f_xs.render(info, True, MINT), (16, 126))
        self.draw_footer("Z/C:Pt  Tab:Time/Temp  [,]:Adj  A:Add  D:Del  Enter/S:Save  N:New")

    def _draw_modal_curve_gen(self) -> None:
        s = self.screen
        u = self.ble.unit_str
        is_f = self.ble.is_fahrenheit
        self._draw_modal_box("AUTO-GENERATE TEMPERATURE CURVE", "ESC: Cancel")

        su = c_to_f(self.cg_start) if is_f else self.cg_start
        eu = c_to_f(self.cg_end) if is_f else self.cg_end
        shape_name = GEN_SHAPES[self.cg_shape_idx][1]

        fields = [
            ("START TEMP", f"< {su}{u} >"),
            ("END TEMP", f"< {eu}{u} >"),
            ("DURATION", f"< {self.cg_dur}s >"),
            ("CURVE SHAPE", f"< {shape_name} >"),
        ]
        for idx, (lbl, val) in enumerate(fields):
            col = idx % 2
            row = idx // 2
            px = 14 + col * 148
            py = 52 + row * 34
            foc = idx == self.cg_focus
            pygame.draw.rect(s, BG, (px, py, 144, 30), border_radius=5)
            pygame.draw.rect(s, MINT if foc else BORDER, (px, py, 144, 30), width=1, border_radius=5)
            s.blit(self.f_xs.render(lbl, True, SUBTEXT), (px + 6, py + 3))
            s.blit(self.f_xs_b.render(val[:22], True, MINT if foc else TEXT), (px + 6, py + 15))

        btn = (14, 123, 292, 22)
        pygame.draw.rect(s, MINT, btn, border_radius=5)
        if self.cg_focus == 4:
            pygame.draw.rect(s, TEXT, btn, width=2, border_radius=5)
        bt = self.f_xs_b.render("GENERATE CURVE BREAKPOINTS [Enter]", True, BG)
        s.blit(bt, (160 - bt.get_width() // 2, 128))
        self.draw_footer("F/X:Field  [,]:Adjust Value  Enter:Generate")

    def _draw_modal_ble_log(self) -> None:
        s = self.screen
        hide_str = "ON" if self.ble.hide_spam_logs else "OFF"
        self._draw_modal_box("BLE PACKET LOG (0x001b / 0x001f)", f"H:Filter99({hide_str}) C:Clear")

        with self.ble.lock:
            entries = list(self.ble.logs)

        if not entries:
            s.blit(self.f_sm.render("No BLE packets logged yet.", True, SUBTEXT), (20, 78))
        else:
            visible = entries[max(0, len(entries) - 7 - self.log_scroll) : len(entries) - self.log_scroll]
            y = 50
            for ts, dirc, msg in visible:
                col = BLUE if dirc == "TX" else (MINT if dirc == "RX" else WARN)
                line = f"[{ts}] {dirc}: {msg}"
                s.blit(self.f_mono.render(line[:52], True, col), (12, y))
                y += 14

        self.draw_footer("F/X:Scroll  T:Send 0xdd Sync  H:Toggle 0x99 Filter  C:Clear  ESC:Back")

    def _draw_modal_rename(self) -> None:
        s = self.screen
        is_curve = self.rename_target == "CURVE"
        title = "RENAME TEMPERATURE CURVE" if is_curve else "RENAME CARTA DEVICE (0xac + 0xaf)"
        sh_active = self.shift_down or self.shift_latch
        right_lbl = "[SHIFT ON]" if sh_active else ("Max 24 chars" if is_curve else "Max 29 chars")
        self._draw_modal_box(title, right_lbl)
        s.blit(self.f_xs.render("Shift: A-Z / Symbols  •  Backspace: Del  •  Enter: Save", True, SUBTEXT), (16, 56))
        box = (16, 76, 288, 30)
        pygame.draw.rect(s, BG, box, border_radius=6)
        pygame.draw.rect(s, MINT, box, width=2, border_radius=6)
        s.blit(self.f_md.render(self.rename_buf + "_", True, TEXT), (24, 83))

        btn = (16, 116, 288, 24)
        pygame.draw.rect(s, MINT, btn, border_radius=6)
        btn_lbl = "SAVE CURVE NAME [Enter]" if is_curve else "SAVE DEVICE NAME [Enter]"
        bt = self.f_sm_b.render(btn_lbl, True, BG)
        s.blit(bt, (160 - bt.get_width() // 2, 122))
        self.draw_footer("Type Name  Backspace:Del  Enter:Save Name  ESC:Cancel")

    def _draw_modal_power_off(self) -> None:
        s = self.screen
        self._draw_modal_box("POWER OFF CARTA?", "0x11 Byte 2 = 0xaf")
        s.blit(self.f_sm.render(f"Send remote shutdown command to {self.ble.device_name}?", True, TEXT), (20, 62))
        s.blit(self.f_xs.render("This turns off the Carta and disconnects Bluetooth.", True, SUBTEXT), (20, 82))

        btn = (20, 112, 280, 26)
        pygame.draw.rect(s, DANGER, btn, border_radius=6)
        bt = self.f_sm_b.render("CONFIRM POWER OFF [Enter]", True, TEXT)
        s.blit(bt, (160 - bt.get_width() // 2, 118))
        self.draw_footer("Enter:Confirm Shutdown  ESC:Cancel")

    # ==========================================================================
    # KEYBOARD INPUT ROUTING
    # ==========================================================================
    def handle_events(self) -> None:
        now = time.time()
        if self.kbd_fds:
            r, _, _ = select.select(self.kbd_fds, [], [], 0.0)
            for fd in r:
                while True:
                    try:
                        data = os.read(fd, 24)
                        if len(data) < 24:
                            break
                        _, _, ev_type, code, value = struct.unpack("llHHi", data)
                        if ev_type == 1:
                            if code in (KEY_LEFTSHIFT, KEY_RIGHTSHIFT):
                                if value == 1:
                                    self.shift_down = True
                                    self.shift_used = False
                                elif value == 0:
                                    self.shift_down = False
                                    if not self.shift_used:
                                        self.shift_latch = not self.shift_latch
                            elif code == KEY_ESC:
                                if value == 1:
                                    self.esc_down_at = now
                                elif value == 0:
                                    if self.esc_down_at is not None and (now - self.esc_down_at) < 0.8:
                                        self._on_short_esc()
                                    self.esc_down_at = None
                            elif value in (1, 2):
                                self.on_key_press(code)
                    except BlockingIOError:
                        break
                    except Exception:
                        break

        if self.esc_down_at is not None and (now - self.esc_down_at) >= 2.0:
            self.running = False

    def _on_short_esc(self) -> None:
        if self.modal is not None:
            self.modal = None
        else:
            self.show_toast("Hold ESC for 2s to exit OpenCartaZero", 1.5)

    def on_key_press(self, code: int) -> None:
        # Modal routing first
        if self.modal == "RENAME":
            self._key_modal_rename(code)
            return
        if self.modal == "POWER_OFF":
            if code == KEY_ENTER:
                self.ble.power_off()
                self.modal = None
                self.show_toast("Sent 0x11 0xaf Power Off!")
            return
        if self.modal == "SESH_PRESET":
            self._key_modal_sesh_preset(code)
            return
        if self.modal == "LED_EDITOR":
            self._key_modal_led_editor(code)
            return
        if self.modal == "CURVE_EDIT":
            self._key_modal_curve_edit(code)
            return
        if self.modal == "CURVE_GEN":
            self._key_modal_curve_gen(code)
            return
        if self.modal == "BLE_LOG":
            self._key_modal_ble_log(code)
            return

        # Global Top-Level Tab Hotkeys (1..4 or Tab)
        if code == KEY_1:
            self.tab_idx = 0
            return
        if code == KEY_2:
            self.tab_idx = 1
            return
        if code == KEY_3:
            self.tab_idx = 2
            return
        if code == KEY_4:
            self.tab_idx = 3
            return
        if code == KEY_TAB:
            self.tab_idx = (self.tab_idx + 1) % 4
            return

        # Dispatch to active tab
        if self.tab_idx == 0:
            self._key_tab_connect(code)
        elif self.tab_idx == 1:
            self._key_tab_home(code)
        elif self.tab_idx == 2:
            self._key_tab_curves(code)
        elif self.tab_idx == 3:
            self._key_tab_device(code)

    def _key_tab_connect(self, code: int) -> None:
        if code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.conn_focus = (self.conn_focus - 1) % 3
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.conn_focus = (self.conn_focus + 1) % 3
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_Z, KEY_LEFT):
            self.conn_sel = max(0, self.conn_sel - 1)
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_C, KEY_RIGHT):
            self.conn_sel += 1
        elif code == KEY_R:
            self.ble.user_disconnected = True
            self.ble.start_scan()
        elif code == KEY_A:
            self.ble.show_all_ble = not self.ble.show_all_ble
            self.ble.refresh_scanned_devices()
        elif code == KEY_O:
            self.ble.user_disconnected = True
            self.tab_idx = 1
            self.show_toast("Offline / Demo Mode")
        elif code in (KEY_ENTER, KEY_SPACE):
            if self.conn_focus == 1:
                self.ble.show_all_ble = not self.ble.show_all_ble
                self.ble.refresh_scanned_devices()
            elif self.conn_focus == 2:
                self.ble.user_disconnected = True
                self.tab_idx = 1
            else:
                if self.ble.is_connected:
                    self.ble.disconnect()
                else:
                    with self.ble.lock:
                        devs = list(self.ble.scanned_devices)
                    if devs:
                        self.ble.connect_device(devs[self.conn_sel % len(devs)])
                    else:
                        self.ble.start_scan()

    def _key_tab_home(self, code: int) -> None:
        min_t = 300 if self.ble.is_fahrenheit else 150
        max_t = 650 if self.ble.is_fahrenheit else 340

        if code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.home_focus = (self.home_focus - 1) % 5
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.home_focus = (self.home_focus + 1) % 5
        elif code == KEY_P:
            self._load_sp_draft(self.ble.active_heat_preset)
            self.modal = "SESH_PRESET"
        elif code == KEY_L:
            self.le_slot = max(1, self.ble.active_led_preset)
            self.modal = "LED_EDITOR"
        elif code == KEY_U:
            self.ble.toggle_unit()
        elif code == KEY_SPACE:
            self._toggle_session()
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS, KEY_Z, KEY_LEFT):
            if self.home_focus == 0:
                self.ble.select_heat_preset(max(1, self.ble.active_heat_preset - 1))
            elif self.home_focus == 1:
                self.ble.set_led_slot(max(0, self.ble.active_led_preset - 1))
            elif self.home_focus == 2:
                nt = max(min_t, self.ble.wax_temp - 5)
                self.ble.send_cc(0x00, preset_slot=0, wax_temp=nt)
            elif self.home_focus == 3:
                ns = max(10, self.ble.wax_timer_sec - 5)
                self.ble.send_cc(0x00, preset_slot=0, wax_timer=ns)
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL, KEY_C, KEY_RIGHT):
            if self.home_focus == 0:
                self.ble.select_heat_preset(min(5, self.ble.active_heat_preset + 1))
            elif self.home_focus == 1:
                self.ble.set_led_slot(min(5, self.ble.active_led_preset + 1))
            elif self.home_focus == 2:
                nt = min(max_t, self.ble.wax_temp + 5)
                self.ble.send_cc(0x00, preset_slot=0, wax_temp=nt)
            elif self.home_focus == 3:
                ns = min(120, self.ble.wax_timer_sec + 5)
                self.ble.send_cc(0x00, preset_slot=0, wax_timer=ns)
        elif code == KEY_ENTER:
            if self.home_focus == 0:
                self._load_sp_draft(self.ble.active_heat_preset)
                self.modal = "SESH_PRESET"
            elif self.home_focus == 1:
                self.le_slot = max(1, self.ble.active_led_preset)
                self.modal = "LED_EDITOR"
            else:
                self._toggle_session()

    def _toggle_session(self) -> None:
        if self.ble.is_session_active:
            self.ble.send_cc(0xAF)
            if not self.ble.is_connected:
                self.ble.remaining_sec = 0
            self.show_toast("Session Stopped (0xaf)")
        else:
            if self.ble.is_connected and not self.ble.has_atomizer:
                self.show_toast("No atomizer detected!")
                return
            self.ble.send_cc(0xA5)
            if not self.ble.is_connected:
                self.ble.remaining_sec = self.ble.wax_timer_sec
            self.show_toast(f"Heating to {self.ble.wax_temp}{self.ble.unit_str} (0xa5)")

    def _key_tab_curves(self, code: int) -> None:
        if code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.curve_focus = (self.curve_focus - 1) % 5
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.curve_focus = (self.curve_focus + 1) % 5
        elif code == KEY_M:
            c = self.active_curve
            c["mode"] = "step" if c["mode"] == "smooth" else "smooth"
            self._save_custom_curves()
        elif code == KEY_E:
            self.modal = "CURVE_EDIT"
        elif code == KEY_G:
            self.modal = "CURVE_GEN"
        elif code == KEY_R:
            self.rename_target = "CURVE"
            self.rename_buf = self.active_curve["name"][:24]
            self.modal = "RENAME"
        elif code == KEY_N:
            new_c = {
                "id": f"custom_{int(time.time())}",
                "name": f"Custom {len([x for x in self.curves if x.get('custom')]) + 1}",
                "mode": self.active_curve["mode"],
                "desc": "Custom saved curve.",
                "pointsC": [[p[0], p[1]] for p in self.active_curve["pointsC"]],
                "custom": True,
            }
            self.curves.append(new_c)
            self.curve_idx = len(self.curves) - 1
            self._save_custom_curves()
            self.rename_target = "CURVE"
            self.rename_buf = new_c["name"]
            self.modal = "RENAME"
        elif code in (KEY_D, KEY_BACKSPACE):
            if len(self.curves) > 1:
                removed = self.active_curve["name"]
                self.curves.pop(self.curve_idx % len(self.curves))
                self.curve_idx = self.curve_idx % len(self.curves)
                self._save_custom_curves()
                self.show_toast(f"Deleted {removed}")
            else:
                self.show_toast("Cannot delete last curve!")
        elif code == KEY_SPACE:
            if self.curve_running:
                self.stop_curve_session()
            else:
                self.start_curve_session()
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_Z, KEY_LEFT):
            if self.curve_focus == 0:
                self.curve_idx = (self.curve_idx - 1) % len(self.curves)
                self._save_custom_curves()
            elif self.curve_focus == 1:
                c = self.active_curve
                c["mode"] = "step" if c["mode"] == "smooth" else "smooth"
                self._save_custom_curves()
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_C, KEY_RIGHT):
            if self.curve_focus == 0:
                self.curve_idx = (self.curve_idx + 1) % len(self.curves)
                self._save_custom_curves()
            elif self.curve_focus == 1:
                c = self.active_curve
                c["mode"] = "step" if c["mode"] == "smooth" else "smooth"
                self._save_custom_curves()
        elif code == KEY_ENTER:
            if self.curve_focus == 0:
                self.curve_idx = (self.curve_idx + 1) % len(self.curves)
                self._save_custom_curves()
            elif self.curve_focus == 1:
                c = self.active_curve
                c["mode"] = "step" if c["mode"] == "smooth" else "smooth"
                self._save_custom_curves()
            elif self.curve_focus == 2:
                self.modal = "CURVE_EDIT"
            elif self.curve_focus == 3:
                self.modal = "CURVE_GEN"
            elif self.curve_focus == 4:
                if self.curve_running:
                    self.stop_curve_session()
                else:
                    self.start_curve_session()

    def _key_tab_device(self, code: int) -> None:
        if code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.dev_focus = (self.dev_focus - 3) % 9
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.dev_focus = (self.dev_focus + 3) % 9
        elif code in (KEY_Z, KEY_LEFT):
            self.dev_focus = (self.dev_focus - 1) % 9
        elif code in (KEY_C, KEY_RIGHT):
            self.dev_focus = (self.dev_focus + 1) % 9
        elif code == KEY_U:
            self.ble.toggle_unit()
        elif code == KEY_L:
            self.modal = "BLE_LOG"
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS):
            self._adjust_device_item(-1)
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL):
            self._adjust_device_item(1)
        elif code in (KEY_ENTER, KEY_SPACE):
            self._activate_device_item()

    def _adjust_device_item(self, delta: int) -> None:
        if self.dev_focus == 0:
            self.ble.toggle_low_power()
        elif self.dev_focus == 1:
            self.ble.toggle_unit()
        elif self.dev_focus == 2:
            step = max(1, min(5, (self.ble.vibe_level // 2) + delta))
            self.ble.set_vibe_step(step)
        elif self.dev_focus == 3:
            sm = max(1, min(15, (self.ble.sleep_timeout_sec // 60) + delta))
            lm = max(1, min(15, self.ble.led_timeout_sec // 60))
            self.ble.send_timeouts(lm, sm)
        elif self.dev_focus == 4:
            sm = max(1, min(15, self.ble.sleep_timeout_sec // 60))
            lm = max(1, min(15, (self.ble.led_timeout_sec // 60) + delta))
            self.ble.send_timeouts(lm, sm)

    def _activate_device_item(self) -> None:
        if self.dev_focus in (0, 1):
            self._adjust_device_item(1)
        elif self.dev_focus in (2, 3, 4):
            self._adjust_device_item(1)
        elif self.dev_focus == 5:
            self.ble.send_time_sync()
            self.show_toast("Sent 0xdd Time Sync!")
        elif self.dev_focus == 6:
            self.rename_target = "DEVICE"
            self.rename_buf = self.ble.device_name[:29]
            self.modal = "RENAME"
        elif self.dev_focus == 7:
            self.modal = "BLE_LOG"
        elif self.dev_focus == 8:
            self.modal = "POWER_OFF"

    # Modal Key Handlers
    def _load_sp_draft(self, slot: int) -> None:
        self.sp_slot = max(1, min(5, slot))
        wtbl = self.ble.presets_f if self.ble.is_fahrenheit else self.ble.presets_c
        htbl = self.ble.herb_presets_f if self.ble.is_fahrenheit else self.ble.herb_presets_c
        self.sp_wax_temp, self.sp_wax_timer = wtbl.get(self.sp_slot, (self.ble.wax_temp, self.ble.wax_timer_sec))
        self.sp_herb_temp, self.sp_herb_timer = htbl.get(self.sp_slot, (self.ble.herb_temp, self.ble.herb_timer_sec))

    def _key_modal_sesh_preset(self, code: int) -> None:
        if code in (KEY_1, KEY_2, KEY_3, KEY_4, KEY_5):
            self._load_sp_draft(code - KEY_1 + 1)
        elif code == KEY_M:
            self.sp_herb = not self.sp_herb
        elif code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.sp_focus = (self.sp_focus - 1) % 4
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.sp_focus = (self.sp_focus + 1) % 4
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS, KEY_Z, KEY_LEFT):
            min_w = 300 if self.ble.is_fahrenheit else 150
            min_h = 200 if self.ble.is_fahrenheit else 100
            if self.sp_focus == 0:
                self._load_sp_draft(max(1, self.sp_slot - 1))
            elif self.sp_focus == 1:
                if self.sp_herb:
                    self.sp_herb_temp = max(min_h, self.sp_herb_temp - 5)
                else:
                    self.sp_wax_temp = max(min_w, self.sp_wax_temp - 5)
            elif self.sp_focus == 2:
                if self.sp_herb:
                    self.sp_herb_timer = max(30, self.sp_herb_timer - 5)
                else:
                    self.sp_wax_timer = max(10, self.sp_wax_timer - 5)
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL, KEY_C, KEY_RIGHT):
            max_w = 650 if self.ble.is_fahrenheit else 340
            max_h = 450 if self.ble.is_fahrenheit else 232
            if self.sp_focus == 0:
                self._load_sp_draft(min(5, self.sp_slot + 1))
            elif self.sp_focus == 1:
                if self.sp_herb:
                    self.sp_herb_temp = min(max_h, self.sp_herb_temp + 5)
                else:
                    self.sp_wax_temp = min(max_w, self.sp_wax_temp + 5)
            elif self.sp_focus == 2:
                if self.sp_herb:
                    self.sp_herb_timer = min(240, self.sp_herb_timer + 5)
                else:
                    self.sp_wax_timer = min(120, self.sp_wax_timer + 5)
        elif code == KEY_ENTER:
            self.ble.send_cc(
                0x00,
                preset_slot=self.sp_slot,
                wax_temp=self.sp_wax_temp,
                wax_timer=self.sp_wax_timer,
                herb_temp=self.sp_herb_temp,
                herb_timer=self.sp_herb_timer,
            )
            self.modal = None
            self.show_toast(f"Saved Preset #{self.sp_slot}")

    def _key_modal_led_editor(self, code: int) -> None:
        cfg = self.ble.led_presets.get(self.le_slot, {"mode": 0x13, "colors": [0x1ED7A6] * 5})
        if code == KEY_0:
            self.ble.set_led_slot(0)
            self.show_toast("LEDs OFF (Stealth)")
        elif code in (KEY_1, KEY_2, KEY_3, KEY_4, KEY_5):
            self.le_slot = code - KEY_1 + 1
            self.ble.set_led_slot(self.le_slot)
        elif code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.le_focus = (self.le_focus - 1) % 4
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.le_focus = (self.le_focus + 1) % 4
        elif code in (KEY_Z, KEY_LEFT):
            if self.le_focus == 2:
                self.le_stop_idx = (self.le_stop_idx - 1) % 5
            elif self.le_focus == 0:
                self.le_slot = max(1, self.le_slot - 1)
                self.ble.set_led_slot(self.le_slot)
        elif code in (KEY_C, KEY_RIGHT):
            if self.le_focus == 2:
                self.le_stop_idx = (self.le_stop_idx + 1) % 5
            elif self.le_focus == 0:
                self.le_slot = min(5, self.le_slot + 1)
                self.ble.set_led_slot(self.le_slot)
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS):
            if self.le_focus == 1:
                cur_i = next((i for i, m in enumerate(LED_MODES) if m[0] == cfg["mode"]), 0)
                cfg["mode"] = LED_MODES[(cur_i - 1) % len(LED_MODES)][0]
            elif self.le_focus == 2:
                cur_c = cfg["colors"][self.le_stop_idx]
                ci = next((i for i, p in enumerate(COLOR_PALETTE) if p[0] == cur_c), 0)
                cfg["colors"][self.le_stop_idx] = COLOR_PALETTE[(ci - 1) % len(COLOR_PALETTE)][0]
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL):
            if self.le_focus == 1:
                cur_i = next((i for i, m in enumerate(LED_MODES) if m[0] == cfg["mode"]), 0)
                cfg["mode"] = LED_MODES[(cur_i + 1) % len(LED_MODES)][0]
            elif self.le_focus == 2:
                cur_c = cfg["colors"][self.le_stop_idx]
                ci = next((i for i, p in enumerate(COLOR_PALETTE) if p[0] == cur_c), 0)
                cfg["colors"][self.le_stop_idx] = COLOR_PALETTE[(ci + 1) % len(COLOR_PALETTE)][0]
        elif code == KEY_ENTER:
            self.ble.send_led_preset_config(self.le_slot, cfg["mode"], cfg["colors"])
            self.modal = None
            self.show_toast(f"Uploaded LED Slot #{self.le_slot}")

    def _key_modal_curve_edit(self, code: int) -> None:
        pts = self.active_curve["pointsC"]
        self.ce_pt_idx = self.ce_pt_idx % len(pts)
        if code in (KEY_Z, KEY_LEFT):
            self.ce_pt_idx = (self.ce_pt_idx - 1) % len(pts)
        elif code in (KEY_C, KEY_RIGHT):
            self.ce_pt_idx = (self.ce_pt_idx + 1) % len(pts)
        elif code == KEY_TAB:
            self.ce_field = 1 - self.ce_field
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS, KEY_X, KEY_DOWN):
            if self.ce_field == 0:
                pts[self.ce_pt_idx][0] = max(0, pts[self.ce_pt_idx][0] - 2)
                pts.sort(key=lambda x: x[0])
            else:
                pts[self.ce_pt_idx][1] = max(150, pts[self.ce_pt_idx][1] - 2)
            self._save_custom_curves()
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL, KEY_F, KEY_UP):
            if self.ce_field == 0:
                pts[self.ce_pt_idx][0] = min(120, pts[self.ce_pt_idx][0] + 2)
                pts.sort(key=lambda x: x[0])
            else:
                pts[self.ce_pt_idx][1] = min(340, pts[self.ce_pt_idx][1] + 2)
            self._save_custom_curves()
        elif code == KEY_A and len(pts) < 6:
            last_t, last_c = pts[-1]
            pts.append([min(120, last_t + 10), last_c])
            self._save_custom_curves()
        elif code == KEY_D and len(pts) > 2:
            pts.pop(self.ce_pt_idx)
            self.ce_pt_idx = min(self.ce_pt_idx, len(pts) - 1)
            self._save_custom_curves()
        elif code == KEY_R:
            self.rename_target = "CURVE"
            self.rename_buf = self.active_curve["name"][:24]
            self.modal = "RENAME"
        elif code == KEY_N:
            new_c = {
                "id": f"custom_{int(time.time())}",
                "name": f"Custom {len([x for x in self.curves if x.get('custom')]) + 1}",
                "mode": self.active_curve["mode"],
                "desc": "Custom saved curve.",
                "pointsC": [[p[0], p[1]] for p in pts],
                "custom": True,
            }
            self.curves.append(new_c)
            self.curve_idx = len(self.curves) - 1
            self._save_custom_curves()
            self.rename_target = "CURVE"
            self.rename_buf = new_c["name"]
            self.modal = "RENAME"
        elif code in (KEY_S, KEY_ENTER):
            self._save_custom_curves()
            self.modal = None
            self.show_toast(f"Saved {self.active_curve['name']}!")

    def _key_modal_curve_gen(self, code: int) -> None:
        if code in (KEY_F, KEY_UP, KEY_SEMICOLON):
            self.cg_focus = (self.cg_focus - 1) % 5
        elif code in (KEY_X, KEY_DOWN, KEY_DOT):
            self.cg_focus = (self.cg_focus + 1) % 5
        elif code in (KEY_LEFTBRACE, KEY_COMMA, KEY_MINUS, KEY_Z, KEY_LEFT):
            if self.cg_focus == 0:
                self.cg_start = max(150, self.cg_start - 3)
            elif self.cg_focus == 1:
                self.cg_end = max(150, self.cg_end - 3)
            elif self.cg_focus == 2:
                self.cg_dur = max(15, self.cg_dur - 5)
            elif self.cg_focus == 3:
                self.cg_shape_idx = (self.cg_shape_idx - 1) % len(GEN_SHAPES)
        elif code in (KEY_RIGHTBRACE, KEY_SLASH, KEY_EQUAL, KEY_C, KEY_RIGHT):
            if self.cg_focus == 0:
                self.cg_start = min(340, self.cg_start + 3)
            elif self.cg_focus == 1:
                self.cg_end = min(340, self.cg_end + 3)
            elif self.cg_focus == 2:
                self.cg_dur = min(120, self.cg_dur + 5)
            elif self.cg_focus == 3:
                self.cg_shape_idx = (self.cg_shape_idx + 1) % len(GEN_SHAPES)
        elif code == KEY_ENTER:
            shape_id = GEN_SHAPES[self.cg_shape_idx][0]
            s_c, e_c, dur = self.cg_start, self.cg_end, self.cg_dur
            pts = []
            mode = "smooth"
            if shape_id == "linear":
                pts = [[0, s_c], [dur, e_c]]
            elif shape_id == "ladder":
                mode = "step"
                mid = int(round((s_c + e_c) / 2.0))
                pts = [[0, s_c], [int(dur * 0.33), mid], [int(dur * 0.68), e_c], [dur, e_c]]
            elif shape_id == "exp":
                k = 2.6
                denom = 1.0 - math.exp(-k)
                for i in range(6):
                    u = i / 5.0
                    fac = (math.exp(-k * u) - math.exp(-k)) / denom
                    pts.append([int(round(u * dur)), int(round(e_c + (s_c - e_c) * fac))])
            else:
                for i in range(6):
                    u = i / 5.0
                    pts.append([int(round(u * dur)), int(round(s_c + (e_c - s_c) * (u * u)))])
            self.active_curve["pointsC"] = pts
            self.active_curve["mode"] = mode
            self._save_custom_curves()
            self.modal = None
            self.show_toast("Generated & Saved Curve!")

    def _key_modal_ble_log(self, code: int) -> None:
        if code in (KEY_F, KEY_UP):
            self.log_scroll = min(max(0, len(self.ble.logs) - 7), self.log_scroll + 1)
        elif code in (KEY_X, KEY_DOWN):
            self.log_scroll = max(0, self.log_scroll - 1)
        elif code == KEY_H:
            self.ble.hide_spam_logs = not self.ble.hide_spam_logs
        elif code == KEY_C:
            self.ble.logs.clear()
        elif code == KEY_T:
            self.ble.send_time_sync()

    def _key_modal_rename(self, code: int) -> None:
        max_len = 24 if self.rename_target == "CURVE" else 29
        if code == KEY_BACKSPACE:
            self.rename_buf = self.rename_buf[:-1]
        elif code == KEY_ENTER:
            clean = self.rename_buf.strip()[:max_len]
            if self.rename_target == "CURVE":
                if clean:
                    self.active_curve["name"] = clean
                    self._save_custom_curves()
                self.modal = None
                self.show_toast(f"Curve: {self.active_curve['name']}")
            else:
                self.ble.send_rename(self.rename_buf)
                self.modal = None
                self.show_toast(f"Renamed to {self.ble.device_name}")
        elif code in KEY_TO_CHAR and len(self.rename_buf) < max_len:
            if self.shift_down or self.shift_latch:
                self.rename_buf += KEY_TO_CHAR_SHIFT.get(code, KEY_TO_CHAR[code].upper())
                self.shift_used = True
                self.shift_latch = False
            else:
                self.rename_buf += KEY_TO_CHAR[code]

    # ==========================================================================
    # MAIN LOOP & PREVIEW RENDERER
    # ==========================================================================
    def render_frame(self) -> None:
        self.screen.fill(BG)
        self.draw_header()
        if self.modal is not None:
            self.draw_modal()
        elif self.tab_idx == 0:
            self.draw_connect()
        elif self.tab_idx == 1:
            self.draw_home()
        elif self.tab_idx == 2:
            self.draw_curves()
        elif self.tab_idx == 3:
            self.draw_device()

    def run(self) -> None:
        if self.preview_out:
            # Populate realistic mock state for screenshots
            self.ble.status = "CONNECTED"
            self.ble.device_name = "Pfeifi McDabface"
            self.ble.device_address = "A4:C1:38:F6:6D:B7"
            self.ble.serial_number = "S26CB1723"
            self.ble.firmware_version = "PROD-030426"
            self.ble.battery_percent = 82
            self.ble.current_temp = 218
            self.ble.wax_temp = 230
            self.ble.wax_timer_sec = 55
            self.ble.dab_counter_1 = 42
            self.ble.scanned_devices = [
                {
                    "path": "/org/bluez/hci0/dev_A4_C1_38_F6_6D_B7",
                    "address": "A4:C1:38:F6:6D:B7",
                    "name": "Pfeifi McDabface",
                    "rssi": -54,
                    "is_carta": True,
                    "battery": 82,
                    "model": "S3BL",
                    "serial": "S26CB1723",
                }
            ]
            if self.preview_tab == "connect":
                self.ble.status = "DISCONNECTED"
                self.tab_idx = 0
            elif self.preview_tab == "home":
                self.tab_idx = 1
            elif self.preview_tab == "curves":
                self.tab_idx = 2
                self.curve_running = True
                self.curve_phase = "ACTIVE"
                self.curve_elapsed = 24
                self.curve_trace = [(t, 245 - int(t * 0.7)) for t in range(0, 26, 2)]
            elif self.preview_tab == "device":
                self.tab_idx = 3
            self.render_frame()
            pygame.image.save(self.screen, self.preview_out)
            return

        try:
            while self.running:
                t0 = time.time()
                self.handle_events()
                self.step_offline_simulation()
                self.render_frame()
                self.flush_fb()
                dt = time.time() - t0
                if dt < 0.04:
                    time.sleep(0.04 - dt)
        finally:
            self.ble.mark_clean_exit()
            for fd in self.kbd_fds:
                try:
                    os.close(fd)
                except Exception:
                    pass
            if self.fb_fd is not None:
                try:
                    os.close(self.fb_fd)
                except Exception:
                    pass


if __name__ == "__main__":
    p_out = None
    p_tab = "home"
    if len(sys.argv) >= 3 and sys.argv[1] == "--preview":
        p_out = sys.argv[2]
        if len(sys.argv) >= 4:
            p_tab = sys.argv[3]
    OpenCartaZeroApp(preview_out=p_out, preview_tab=p_tab).run()
