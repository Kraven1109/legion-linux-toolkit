#!/usr/bin/env python3
"""
legion_core — Consolidated Hardware & Platform Core Library for Lenovo Legion Linux Toolkit
Target Device: Lenovo Legion Pro 7 16IAX10H (Type 83F5, CachyOS Linux)

Single authoritative source of truth for:
- Sysfs & ACPI hardware paths
- Platform power & thermal profile definitions
- Display EDID panel detection & factory ICC color profile definitions
- Zero-overhead native telemetry (NVML ctypes, RAPL energy_uj, lenovo_wmi_other fans)
- Wayland / KDE Plasma 6 desktop session recovery
"""

import os
import sys
import glob
import json
import time
import struct
import shutil
import ctypes
import signal
import select
import subprocess
import re
from typing import Dict, Any, Optional, Tuple, List

# --- Hardware Paths & System Nodes ---

PLATFORM_PROFILE_NODE = "/sys/firmware/acpi/platform_profile"
PLATFORM_PROFILE_CHOICES_NODE = "/sys/firmware/acpi/platform_profile_choices"
CONSERVATION_MODE_NODE = "/sys/devices/pci0000:00/0000:00:1f.0/PNP0C09:00/VPC2004:00/conservation_mode"
BATTERY_DIR = "/sys/class/power_supply/BAT0"
RAPL_ENERGY_NODE = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_MMIO_DIR = "/sys/devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0"
RAPL_MMIO_PL1_NODE = os.path.join(RAPL_MMIO_DIR, "constraint_0_power_limit_uw")
RAPL_MMIO_PL2_NODE = os.path.join(RAPL_MMIO_DIR, "constraint_1_power_limit_uw")
HOTKEY_NODE = "/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event"

EXPECTED_PANEL_ID = "SDC420B"

CONFIG_DIR = os.path.expanduser("~/.config/legion")
CONFIG_JSONC_PATH = os.path.join(CONFIG_DIR, "config.jsonc")
CONFIG_JSON_PATH = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = os.path.expanduser("~/.cache/legion")
GPU_CACHE_FILE = os.path.join(CACHE_DIR, "gpu_info.json")
ICON_DIR = os.path.expanduser("~/.local/share/icons/legion")
COLOR_PROFILE_DIR = os.path.expanduser("~/.local/share/color/icc")
IPC_SOCKET_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR") or f"/tmp",
    f"legion-profile-osd-{os.getuid()}.sock",
)

# Conservative default MMIO RAPL limits (Watts) per ACPI platform_profile on AC power.
# Addresses Linux kernel boot clamping on Arrow Lake-HX where intel-rapl-mmio:0 defaults to 30W/30W.
DEFAULT_RAPL_MMIO_PROFILES: Dict[str, Dict[str, int]] = {
    "low-power": {"pl1_w": 30, "pl2_w": 30},
    "balanced": {"pl1_w": 45, "pl2_w": 55},
    "performance": {"pl1_w": 55, "pl2_w": 65},
    "max-power": {"pl1_w": 65, "pl2_w": 85},
}
DEFAULT_RAPL_MMIO_BATTERY: Dict[str, int] = {"pl1_w": 30, "pl2_w": 30}
RAPL_MMIO_PL1_BOUNDS_W = (15, 165)
RAPL_MMIO_PL2_BOUNDS_W = (15, 210)

# --- Platform Power & Thermal Profile Definitions ---

PLATFORM_PROFILES: Dict[str, Dict[str, Any]] = {
    "low-power": {
        "id": "low-power",
        "alias": "quiet",
        "title": "Quiet Mode",
        "led": "Blue",
        "led_color_code": "\033[1;34m",
        "msg": "🔵 Blue LED • Silent fans, power-saving",
        "icon_file": "quiet.svg",
        "fallback": "battery-charging",
        "fallback_icon": "battery-charging",
        "desc": "Silent fans, low power draw, battery-saving",
    },
    "balanced": {
        "id": "balanced",
        "alias": "balanced",
        "title": "Balanced Mode",
        "led": "White",
        "led_color_code": "\033[1;37m",
        "msg": "⚪ White LED • Dynamic auto power allocation",
        "icon_file": "balanced.svg",
        "fallback": "battery-profile-balanced",
        "fallback_icon": "battery-profile-balanced",
        "desc": "Dynamic auto power allocation",
    },
    "performance": {
        "id": "performance",
        "alias": "perf",
        "title": "Performance Mode",
        "led": "Red",
        "led_color_code": "\033[1;31m",
        "msg": "🔴 Red LED • Full 175W TGP & High CPU boost",
        "icon_file": "performance.svg",
        "fallback": "preferences-system-performance",
        "fallback_icon": "preferences-system-performance",
        "desc": "Full 175W TGP for RTX 5090 & high CPU boost",
    },
    "max-power": {
        "id": "max-power",
        "alias": "extreme",
        "title": "Extreme Mode",
        "led": "Purple",
        "led_color_code": "\033[1;35m",
        "msg": "🟣 Purple LED • Maximum fan curves & peak power",
        "icon_file": "extreme.svg",
        "fallback": "speedometer",
        "fallback_icon": "speedometer",
        "desc": "Max cooling fan curves & peak overclocking",
    },
    "custom": {
        "id": "custom",
        "alias": "custom",
        "title": "Custom Mode",
        "led": "Cyan",
        "led_color_code": "\033[1;36m",
        "msg": "Custom thermal envelope & curves",
        "icon_file": "custom.svg",
        "fallback": "preferences-system",
        "fallback_icon": "preferences-system",
        "desc": "Requires Lenovo Vantage EC tables [Disabled on Linux]",
    },
}

# --- Calibrated Color Profile Definitions (Samsung SDC420B) ---

COLOR_PROFILES: List[Dict[str, str]] = [
    {
        "id": "srgb",
        "name": "sRGB",
        "file": "TPLCD_420B_sRGB.icm",
        "title": "sRGB (Standard Color)",
        "desc": "Web & Office • Clamped Gamut • Accurate Colors",
    },
    {
        "id": "displayp3",
        "name": "Display P3",
        "file": "TPLCD_420B_DisplayP3.icm",
        "title": "Display P3 (Wide Gamut)",
        "desc": "Modern Media & Apple Standard • Rich Vibrant Gamut",
    },
    {
        "id": "dcip3",
        "name": "DCI-P3",
        "file": "TPLCD_420B_DCIP3.icm",
        "title": "DCI-P3 (Digital Cinema)",
        "desc": "Theatrical & Movie Production • DCI Color Space",
    },
    {
        "id": "adobergb",
        "name": "Adobe RGB",
        "file": "TPLCD_420B_AdobeRGB.icm",
        "title": "Adobe RGB (Print & Photo)",
        "desc": "Expanded Cyan-Green Range • Professional Publishing",
    },
    {
        "id": "rec709",
        "name": "Rec.709",
        "file": "TPLCD_420B_REC709.icm",
        "title": "Rec.709 (HDTV Broadcast)",
        "desc": "Television & Video Broadcast Standard",
    },
    {
        "id": "native",
        "name": "Native",
        "file": "TPLCD_420B_Native.icm",
        "title": "Native (Full OLED)",
        "desc": "Unclamped OLED Gamut • Maximum Hardware Color Space",
    },
]


# --- GUI Environment Recovery (KDE Plasma 6 Wayland) ---

def ensure_gui_environment() -> None:
    """
    Ensures WAYLAND_DISPLAY, DISPLAY, DBUS_SESSION_BUS_ADDRESS, and ~/.local/bin PATH
    are set in os.environ. Essential when scripts/daemons run from minimal environments.
    """
    local_bin = os.path.expanduser("~/.local/bin")
    cur_path = os.environ.get("PATH", "")
    if local_bin not in cur_path.split(os.pathsep):
        os.environ["PATH"] = f"{local_bin}{os.pathsep}{cur_path}" if cur_path else local_bin

    uid = os.getuid()
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    os.environ["XDG_RUNTIME_DIR"] = runtime_dir

    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        bus_path = f"{runtime_dir}/bus"
        if os.path.exists(bus_path):
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"

    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        return

    try:
        res = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True, text=True, timeout=1,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k in (
                        "WAYLAND_DISPLAY", "DISPLAY", "XDG_CURRENT_DESKTOP",
                        "XDG_SESSION_TYPE", "XAUTHORITY", "PATH",
                        "QT_WAYLAND_RECONNECT", "DBUS_SESSION_BUS_ADDRESS",
                    ):
                        os.environ[k] = v
    except Exception:
        pass

    if not os.environ.get("WAYLAND_DISPLAY"):
        sockets = [s for s in glob.glob(f"{runtime_dir}/wayland-*") if not s.endswith(".lock")]
        if sockets:
            os.environ["WAYLAND_DISPLAY"] = os.path.basename(sorted(sockets)[0])

    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"

    if not os.environ.get("XDG_CURRENT_DESKTOP"):
        os.environ["XDG_CURRENT_DESKTOP"] = "KDE"


# --- Hardware Probing & Sysfs Queries ---

def get_panel_info() -> Tuple[Optional[str], Optional[str]]:
    """
    Reads internal eDP display EDID directly from sysfs.
    Extracts Manufacturer ID (bytes 8-9) and Product Code (bytes 10-11).
    Returns (hardware_id, edid_sysfs_path) or (None, None).
    """
    for edid_path in sorted(glob.glob("/sys/class/drm/*-eDP-*/edid")):
        try:
            with open(edid_path, "rb") as f:
                data = f.read()
            if len(data) >= 128:
                mfg = int.from_bytes(data[8:10], "big")
                c1 = chr(((mfg >> 10) & 0x1F) + ord("A") - 1)
                c2 = chr(((mfg >> 5) & 0x1F) + ord("A") - 1)
                c3 = chr((mfg & 0x1F) + ord("A") - 1)
                prod = int.from_bytes(data[10:12], "little")
                hw_id = f"{c1}{c2}{c3}{prod:04X}"
                return hw_id, edid_path
        except Exception:
            continue
    return None, None


# Common 3-letter PNP Manufacturer IDs for external monitors
PNP_MANUFACTURERS: Dict[str, str] = {
    "SDC": "Samsung",
    "SAM": "Samsung",
    "BOE": "BOE",
    "AUO": "AUO",
    "CMN": "Innolux",
    "CSO": "CSOT",
    "SHP": "Sharp",
    "IVM": "Iiyama",
    "DEL": "Dell",
    "GSM": "LG",
    "LGD": "LG",
    "ACR": "Acer",
    "AUS": "ASUS",
    "ASU": "ASUS",
    "BNQ": "BenQ",
    "LEN": "Lenovo",
    "AOC": "AOC",
    "MSI": "MSI",
    "SNY": "Sony",
    "HPN": "HP",
    "HWP": "HP",
    "GIG": "Gigabyte",
    "VSC": "ViewSonic",
    "PHL": "Philips",
}


def parse_edid(data: bytes) -> Optional[Dict[str, str]]:
    """
    Parses a 128+ byte EDID binary structure.
    Extracts 3-letter PNP Manufacturer ID, product code, model name (type 0xFC/0xFE),
    and friendly display title.
    """
    if len(data) < 128:
        return None
    try:
        mfg = int.from_bytes(data[8:10], "big")
        c1 = chr(((mfg >> 10) & 0x1F) + ord("A") - 1)
        c2 = chr(((mfg >> 5) & 0x1F) + ord("A") - 1)
        c3 = chr((mfg & 0x1F) + ord("A") - 1)
        mfg_code = f"{c1}{c2}{c3}"
        prod = int.from_bytes(data[10:12], "little")
        hw_id = f"{mfg_code}{prod:04X}"
        vendor_name = PNP_MANUFACTURERS.get(mfg_code, mfg_code)

        # Scan for human-readable descriptors across the entire EDID payload
        # (Prioritize 0xFC Display Product Name first, then 0xFE Alphanumeric String)
        model_name = None
        for tag in (0xFC, 0xFE):
            target = b"\x00\x00\x00" + bytes([tag])
            idx = 0
            while True:
                found = data.find(target, idx)
                if found == -1:
                    break
                if found + 18 <= len(data):
                    desc = data[found : found + 18]
                    try:
                        cand = desc[5:].split(b"\x0a")[0].decode("ascii", errors="ignore").strip()
                        if cand and len(cand) >= 2 and all(32 <= ord(c) <= 126 for c in cand):
                            model_name = cand
                            break
                    except Exception:
                        pass
                idx = found + 1
            if model_name:
                break
        # For known internal Legion panel, standardize on Samsung SDC420B
        if mfg_code == "SDC" and hw_id == "SDC420B":
            display_title = "Samsung SDC420B"
        elif model_name:
            if model_name.lower().startswith(vendor_name.lower()):
                display_title = model_name
            else:
                display_title = f"{vendor_name} {model_name}"
        else:
            display_title = f"{vendor_name} {hw_id}"

        return {
            "mfg_code": mfg_code,
            "vendor": vendor_name,
            "hw_id": hw_id,
            "model": model_name or hw_id,
            "display_title": display_title,
        }
    except Exception:
        return None


_EDID_CACHE: Dict[str, Dict[str, str]] = {}
_DISPLAY_INFO_CACHE: Optional[Tuple[float, Dict[str, Any]]] = None


def get_active_display_info(ttl: float = 0.0) -> Dict[str, Any]:
    """
    Queries kscreen-doctor -j for all connected and enabled outputs.
    Supports single-display, extended multi-display, and mirrored/cloned setups.
    When ttl > 0 (e.g. in continuous watch loops), reuses cached display state for up to ttl seconds.
    """
    global _DISPLAY_INFO_CACHE
    if ttl > 0.0 and _DISPLAY_INFO_CACHE is not None:
        ts, cached_res = _DISPLAY_INFO_CACHE
        if (time.monotonic() - ts) < ttl:
            return cached_res

    ensure_gui_environment()
    default_disp = {
        "output_name": "eDP-1",
        "id": 1,
        "priority": 1,
        "is_primary": True,
        "is_internal": True,
        "vendor": "Samsung",
        "model": EXPECTED_PANEL_ID,
        "hw_id": EXPECTED_PANEL_ID,
        "display_title": f"Samsung {EXPECTED_PANEL_ID}",
        "icc_profile_path": "",
        "refresh_rate_hz": 240.0,
        "resolution": "2560x1600",
        "scale": 1.5,
        "pos": {"x": 0, "y": 0},
        "replication_source": 0,
    }

    if not shutil.which("kscreen-doctor"):
        res = dict(default_disp)
        res["display_mode"] = "single"
        res["count"] = 1
        res["displays"] = [default_disp]
        return res

    active_displays: List[Dict[str, Any]] = []
    display_mode = "single"

    try:
        proc = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=1)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            outputs = data.get("outputs", [])
            active_outs = [o for o in outputs if o.get("connected") and o.get("enabled")]

            # Detect display mode: mirrored if any clone/replicationSource exists, else extended
            if len(active_outs) > 1:
                is_mirrored = any(
                    o.get("replicationSource") or o.get("clones")
                    for o in active_outs
                )
                display_mode = "mirrored" if is_mirrored else "extended"

            for out in active_outs:
                out_name = out.get("name", "eDP-1")
                is_internal = out_name.startswith("eDP")
                d_info = {
                    "output_name": out_name,
                    "id": out.get("id"),
                    "priority": out.get("priority", 99),
                    "is_primary": out.get("priority") == 1 or (is_internal and out.get("priority") is None),
                    "is_internal": is_internal,
                    "vendor": "Samsung" if is_internal else "External",
                    "model": EXPECTED_PANEL_ID if is_internal else out_name,
                    "hw_id": EXPECTED_PANEL_ID if is_internal else out_name,
                    "display_title": f"Samsung {EXPECTED_PANEL_ID}" if is_internal else f"External ({out_name})",
                    "icc_profile_path": out.get("iccProfilePath") or "",
                    "scale": float(out.get("scale", 1.0)),
                    "pos": out.get("pos", {"x": 0, "y": 0}),
                    "replication_source": out.get("replicationSource", 0),
                    "refresh_rate_hz": 240.0 if is_internal else 60.0,
                    "resolution": "2560x1600" if is_internal else "1920x1080",
                }

                # Find mode details
                mode_matched = False
                curr_mode_id = str(out.get("currentModeId"))
                for m in out.get("modes", []):
                    if str(m.get("id")) == curr_mode_id:
                        d_info["refresh_rate_hz"] = round(float(m.get("refreshRate", 240)), 2)
                        size = m.get("size", {})
                        w = size.get("width")
                        h = size.get("height")
                        if w and h:
                            d_info["resolution"] = f"{w}x{h}"
                        mode_matched = True
                        break
                d_info["_mode_matched"] = mode_matched

                # Resolve EDID and GPU source (dGPU vs iGPU) for this connector
                gpu_source = "iGPU" if is_internal else "dGPU"
                for status_p in glob.glob(f"/sys/class/drm/card*-{out_name}/status"):
                    try:
                        with open(status_p, "r") as sf:
                            if sf.read().strip().lower() == "connected":
                                conn_dir = os.path.dirname(status_p)
                                card_name = os.path.basename(conn_dir).split("-", 1)[0]
                                card_dev_dir = os.path.join("/sys/class/drm", card_name, "device")
                                vend_p = os.path.join(card_dev_dir, "vendor")
                                if os.path.isfile(vend_p):
                                    with open(vend_p, "r") as vf:
                                        v_id = vf.read().strip().lower()
                                        if v_id == "0x10de":
                                            gpu_source = "dGPU"
                                        elif v_id == "0x8086":
                                            gpu_source = "iGPU"
                                        elif v_id == "0x1002":
                                            b_vga_p = os.path.join(card_dev_dir, "boot_vga")
                                            is_boot = False
                                            if os.path.isfile(b_vga_p):
                                                with open(b_vga_p, "r") as bf:
                                                    is_boot = bf.read().strip() == "1"
                                            gpu_source = "iGPU" if is_boot else "dGPU"
                                break
                    except Exception:
                        pass
                d_info["gpu_source"] = gpu_source

                edid_parsed = _EDID_CACHE.get(out_name)
                if edid_parsed is None:
                    for edid_p in glob.glob(f"/sys/class/drm/*-{out_name}/edid"):
                        try:
                            with open(edid_p, "rb") as f:
                                edid_data = f.read()
                            if len(edid_data) >= 128:
                                edid_parsed = parse_edid(edid_data)
                                if edid_parsed:
                                    _EDID_CACHE[out_name] = edid_parsed
                                    break
                        except Exception:
                            continue
                if edid_parsed:
                    d_info["vendor"] = edid_parsed["vendor"]
                    d_info["model"] = edid_parsed["model"]
                    d_info["hw_id"] = edid_parsed["hw_id"]
                    d_info["display_title"] = edid_parsed["display_title"]

                active_displays.append(d_info)
    except Exception:
        pass

    if not active_displays:
        active_displays = [default_disp]

    # Sort: Primary display first (priority 1 or internal), then by output name
    active_displays.sort(key=lambda d: (0 if d["is_primary"] else 1, 0 if d["is_internal"] else 1, d["output_name"]))

    primary = active_displays[0]

    # Regex fallback only when JSON mode lookup failed for the primary output
    if not primary.get("_mode_matched", True) and shutil.which("kscreen-doctor"):
        try:
            proc_o = subprocess.run(["kscreen-doctor", "-o"], capture_output=True, text=True, timeout=1)
            if proc_o.returncode == 0:
                out_pat = rf"Output:\s+\d+\s+{re.escape(primary['output_name'])}\b.*?(?=\nOutput:|\Z)"
                block = re.search(out_pat, proc_o.stdout, flags=re.DOTALL)
                if block:
                    m = re.search(r"@([0-9.]+)\*", block.group(0))
                    if m:
                        primary["refresh_rate_hz"] = round(float(m.group(1)), 2)
        except Exception:
            pass
    for d in active_displays:
        d.pop("_mode_matched", None)

    res = dict(primary)
    res["display_mode"] = display_mode
    res["count"] = len(active_displays)
    res["displays"] = active_displays
    res["internal_display"] = next((d for d in active_displays if d.get("is_internal")), default_disp)
    _DISPLAY_INFO_CACHE = (time.monotonic(), res)
    return res


def get_internal_display() -> Tuple[str, str]:
    """
    Specifically returns the internal eDP panel output name and its active ICC profile path.
    Guarantees returning (internal_name, icc_path) regardless of primary external displays
    or whether the internal eDP panel is currently disabled in clamshell/external-only mode.
    """
    info = get_active_display_info()
    for d in info.get("displays", []):
        if d.get("is_internal"):
            return d.get("output_name", "eDP-1"), d.get("icc_profile_path", "")

    # Fallback: query kscreen-doctor -j for connected (even if disabled) eDP outputs
    if shutil.which("kscreen-doctor"):
        try:
            proc = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=1)
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                for out in data.get("outputs", []):
                    name = out.get("name", "")
                    if out.get("connected") and name.startswith("eDP"):
                        return name, out.get("iccProfilePath") or ""
        except Exception:
            pass
    return "eDP-1", ""


def is_internal_display_enabled() -> bool:
    """Returns True if an internal eDP panel is currently connected AND enabled in KScreen."""
    info = get_active_display_info()
    return any(d.get("is_internal") for d in info.get("displays", []))


def get_active_display() -> Tuple[str, str]:
    """
    Queries kscreen-doctor for the primary connected eDP output.
    Returns (output_name, current_icc_path).
    """
    info = get_active_display_info()
    return info["output_name"], info["icc_profile_path"]


def get_conservation_mode() -> Tuple[bool, str]:
    """
    Reads battery conservation mode node.
    Returns (is_active, node_path).
    """
    node = CONSERVATION_MODE_NODE
    if not os.path.isfile(node):
        matches = glob.glob("/sys/devices/**/conservation_mode", recursive=True)
        if matches:
            node = matches[0]

    if os.path.isfile(node):
        try:
            with open(node, "r") as f:
                return f.read().strip() == "1", node
        except Exception:
            pass
    return False, node


def get_platform_profile() -> Dict[str, Any]:
    """Reads current ACPI platform_profile and returns enriched metadata."""
    node = PLATFORM_PROFILE_NODE
    raw = "unknown"
    if os.path.isfile(node):
        try:
            with open(node, "r") as f:
                raw = f.read().strip()
        except Exception:
            pass

    prof = PLATFORM_PROFILES.get(raw, {
        "id": raw,
        "alias": raw,
        "title": raw.capitalize() + " Mode",
        "led": "Unknown",
        "led_color_code": "\033[0m",
        "msg": raw,
        "icon_file": "balanced.svg",
        "fallback_icon": "battery-profile-balanced",
        "desc": raw,
    })
    return prof


def parse_jsonc(text: str) -> Dict[str, Any]:
    """
    Parses JSON with single-line (//) and multi-line (/* */) comments,
    preserving string literals and stripping trailing commas.
    """
    pattern = r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/'

    def _replace(match):
        if match.group(1):
            return match.group(1)
        return ""

    cleaned = re.sub(pattern, _replace, text, flags=re.DOTALL)
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
    return json.loads(cleaned)


def load_config() -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Reads configuration dynamically from ~/.config/legion/config.jsonc (or config.json).
    Returns (config_dict, error_or_None).
    """
    for path in (CONFIG_JSONC_PATH, CONFIG_JSON_PATH):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return parse_jsonc(f.read()), None
            except Exception as e:
                return {}, f"{os.path.basename(path)} error: {e}"
    return {}, None


def is_ac_online() -> bool:
    """Returns True if any Mains AC power supply reports online=1, or True if none found."""
    mains_found = False
    for psy_dir in sorted(glob.glob("/sys/class/power_supply/*")):
        type_p = os.path.join(psy_dir, "type")
        online_p = os.path.join(psy_dir, "online")
        if os.path.isfile(type_p) and os.path.isfile(online_p):
            try:
                with open(type_p, "r") as ft:
                    if ft.read().strip().lower() == "mains":
                        mains_found = True
                        with open(online_p, "r") as fo:
                            if fo.read().strip() == "1":
                                return True
            except Exception:
                pass
    return not mains_found


def get_rapl_mmio_limits() -> Dict[str, Any]:
    """Reads active MMIO RAPL PL1/PL2 power limits (Watts) from intel-rapl-mmio:0."""
    res: Dict[str, Any] = {
        "available": os.path.isdir(RAPL_MMIO_DIR),
        "enabled": None,
        "pl1_w": None,
        "pl2_w": None,
        "writable": False,
    }
    if not res["available"]:
        return res

    try:
        en_p = os.path.join(RAPL_MMIO_DIR, "enabled")
        if os.path.isfile(en_p):
            with open(en_p, "r") as f:
                res["enabled"] = f.read().strip() == "1"
        if os.path.isfile(RAPL_MMIO_PL1_NODE):
            with open(RAPL_MMIO_PL1_NODE, "r") as f:
                res["pl1_w"] = round(int(f.read().strip()) / 1_000_000.0, 1)
        if os.path.isfile(RAPL_MMIO_PL2_NODE):
            with open(RAPL_MMIO_PL2_NODE, "r") as f:
                res["pl2_w"] = round(int(f.read().strip()) / 1_000_000.0, 1)
        res["writable"] = os.access(RAPL_MMIO_PL1_NODE, os.W_OK) and os.access(RAPL_MMIO_PL2_NODE, os.W_OK)
    except Exception:
        pass
    return res


def _clamp_watts(val: Any, bounds: Tuple[int, int], fallback: int) -> int:
    try:
        num = int(round(float(val)))
    except (TypeError, ValueError):
        num = fallback
    return max(bounds[0], min(bounds[1], num))


def sync_rapl_mmio(profile_id: Optional[str] = None, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Synchronizes intel-rapl-mmio:0 PL1/PL2 constraints to match the active ACPI platform_profile
    and AC/battery power state. Safe, idempotent, and zero-overhead.
    """
    if not os.path.isfile(RAPL_MMIO_PL1_NODE) or not os.path.isfile(RAPL_MMIO_PL2_NODE):
        return {"applied": False, "changed": False, "reason": "sysfs_missing"}

    if cfg is None:
        cfg, _ = load_config()

    rapl_cfg = cfg.get("rapl_mmio", {}) if isinstance(cfg, dict) else {}
    if isinstance(rapl_cfg, dict) and rapl_cfg.get("enabled", True) is False:
        return {"applied": False, "changed": False, "reason": "disabled"}

    if not profile_id and os.path.isfile(PLATFORM_PROFILE_NODE):
        try:
            with open(PLATFORM_PROFILE_NODE, "r") as f:
                profile_id = f.read().strip()
        except Exception:
            profile_id = ""

    default_entry = DEFAULT_RAPL_MMIO_PROFILES.get(profile_id or "")
    if not default_entry:
        return {"applied": False, "changed": False, "reason": "unsupported_profile", "profile": profile_id}

    profiles_cfg = rapl_cfg.get("profiles", {}) if isinstance(rapl_cfg, dict) else {}
    prof_override = profiles_cfg.get(profile_id, {}) if isinstance(profiles_cfg, dict) else {}
    if not isinstance(prof_override, dict):
        prof_override = {}

    pl1_w = _clamp_watts(prof_override.get("pl1_w", default_entry["pl1_w"]), RAPL_MMIO_PL1_BOUNDS_W, default_entry["pl1_w"])
    pl2_w = _clamp_watts(prof_override.get("pl2_w", default_entry["pl2_w"]), RAPL_MMIO_PL2_BOUNDS_W, default_entry["pl2_w"])

    ac_online = is_ac_online()
    if not ac_online:
        bat_cfg = rapl_cfg.get("battery", {}) if isinstance(rapl_cfg, dict) else {}
        if not isinstance(bat_cfg, dict):
            bat_cfg = {}
        bat_pl1 = _clamp_watts(bat_cfg.get("pl1_w", DEFAULT_RAPL_MMIO_BATTERY["pl1_w"]), RAPL_MMIO_PL1_BOUNDS_W, DEFAULT_RAPL_MMIO_BATTERY["pl1_w"])
        bat_pl2 = _clamp_watts(bat_cfg.get("pl2_w", DEFAULT_RAPL_MMIO_BATTERY["pl2_w"]), RAPL_MMIO_PL2_BOUNDS_W, DEFAULT_RAPL_MMIO_BATTERY["pl2_w"])
        pl1_w = min(pl1_w, bat_pl1)
        pl2_w = min(pl2_w, bat_pl2)

    if pl2_w < pl1_w:
        pl2_w = pl1_w

    if not (os.access(RAPL_MMIO_PL1_NODE, os.W_OK) and os.access(RAPL_MMIO_PL2_NODE, os.W_OK)):
        return {"applied": False, "changed": False, "reason": "permission_denied", "profile": profile_id}

    target_pl1_uw = pl1_w * 1_000_000
    target_pl2_uw = pl2_w * 1_000_000

    try:
        with open(RAPL_MMIO_PL1_NODE, "r") as f1, open(RAPL_MMIO_PL2_NODE, "r") as f2:
            cur_pl1_uw = int(f1.read().strip())
            cur_pl2_uw = int(f2.read().strip())

        if cur_pl1_uw == target_pl1_uw and cur_pl2_uw == target_pl2_uw:
            return {
                "applied": True,
                "changed": False,
                "profile": profile_id,
                "ac_online": ac_online,
                "pl1_w": pl1_w,
                "pl2_w": pl2_w,
            }

        with open(RAPL_MMIO_PL1_NODE, "w") as f1:
            f1.write(str(target_pl1_uw))
        with open(RAPL_MMIO_PL2_NODE, "w") as f2:
            f2.write(str(target_pl2_uw))

        return {
            "applied": True,
            "changed": True,
            "profile": profile_id,
            "ac_online": ac_online,
            "pl1_w": pl1_w,
            "pl2_w": pl2_w,
        }
    except Exception as e:
        return {"applied": False, "changed": False, "reason": str(e), "profile": profile_id}


_HWMON_BY_NAME_CACHE: Dict[str, List[str]] = {}


def get_hwmons_by_name(name: str) -> List[str]:
    """Finds all sysfs hwmon directories matching the given device name, with validation cache."""
    cached = _HWMON_BY_NAME_CACHE.get(name)
    if cached and all(os.path.isdir(p) for p in cached):
        return cached

    matches: List[str] = []
    for p in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name_file = os.path.join(p, "name")
        if os.path.isfile(name_file):
            try:
                with open(name_file, "r") as f:
                    if f.read().strip() == name:
                        matches.append(p)
            except Exception:
                pass
    if matches:
        _HWMON_BY_NAME_CACHE[name] = matches
    return matches


def get_hwmon_by_name(name: str) -> Optional[str]:
    """Finds the first sysfs hwmon directory matching the given device name."""
    matches = get_hwmons_by_name(name)
    return matches[0] if matches else None


def get_cooling_fans() -> Dict[str, Any]:
    """
    Queries Lenovo cooling fan telemetry via lenovo_wmi_other or legon_laptop hwmon.
    Supports both triple-fan (CPU fan1, GPU fan2, Aux fan4/fan3) and dual-fan laptops.
    """
    res = {
        "cpu_fan": {"rpm": 0, "max_rpm": 5200, "percent": 0.0, "present": False},
        "gpu_fan": {"rpm": 0, "max_rpm": 5400, "percent": 0.0, "present": False},
        "aux_fan": {"rpm": 0, "max_rpm": 6500, "percent": 0.0, "present": False},
    }

    wmi_dir = get_hwmon_by_name("lenovo_wmi_other") or get_hwmon_by_name("legion")
    if wmi_dir:
        fan_mappings = [
            (["fan1"], "cpu_fan", 5200),
            (["fan2"], "gpu_fan", 5400),
            (["fan4", "fan3"], "aux_fan", 6500),
        ]
        for prefixes, key, default_max in fan_mappings:
            for prefix in prefixes:
                inp = os.path.join(wmi_dir, f"{prefix}_input")
                if not os.path.isfile(inp):
                    continue
                max_f = os.path.join(wmi_dir, f"{prefix}_max")
                rpm = 0
                max_rpm = default_max
                try:
                    with open(inp, "r") as f:
                        rpm = int(f.read().strip())
                except Exception:
                    pass
                if os.path.isfile(max_f):
                    try:
                        with open(max_f, "r") as f:
                            val = int(f.read().strip())
                            if val > 0:
                                max_rpm = val
                    except Exception:
                        pass
                pct = round((rpm / max_rpm) * 100.0, 1) if max_rpm > 0 else 0.0
                res[key] = {"rpm": rpm, "max_rpm": max_rpm, "percent": pct, "present": True}
                break

    return res


def get_spd_ram_temps(ttl: float = 0.0) -> List[float]:
    """Reads DDR5 SPD thermal sensors (spd5118) in degrees Celsius (with optional TTL cache to reduce SMBus I2C traffic)."""
    global _CACHED_SPD_TEMPS, _CACHED_SPD_TIME
    now = time.monotonic()
    if ttl > 0.0 and _CACHED_SPD_TEMPS is not None and (now - _CACHED_SPD_TIME) < ttl:
        return _CACHED_SPD_TEMPS

    temps: List[float] = []
    for hdir in get_hwmons_by_name("spd5118"):
        temp_file = os.path.join(hdir, "temp1_input")
        if os.path.isfile(temp_file):
            try:
                with open(temp_file, "r") as tf:
                    temps.append(round(int(tf.read().strip()) / 1000.0, 1))
            except Exception:
                pass
    _CACHED_SPD_TEMPS = temps
    _CACHED_SPD_TIME = now
    return temps


_CACHED_SYSTEM_MODEL: Optional[str] = None
_CACHED_MEMORY_HARDWARE: Optional[Dict[str, Any]] = None


def get_system_model() -> str:
    """
    Dynamically reads laptop product version and type from DMI sysfs
    (e.g. 'Pro 7 16IAX10H' or 'Legion 5 16IRX9').
    """
    global _CACHED_SYSTEM_MODEL
    if _CACHED_SYSTEM_MODEL is not None:
        return _CACHED_SYSTEM_MODEL

    ver = ""
    name = ""
    for node, attr in (
        ("/sys/class/dmi/id/product_version", "ver"),
        ("/sys/class/dmi/id/product_family", "fam"),
        ("/sys/class/dmi/id/product_name", "name"),
    ):
        if os.path.isfile(node):
            try:
                with open(node, "r") as f:
                    val = f.read().strip()
                    if val and val.lower() not in ("invalid", "none", "to be filled by o.e.m."):
                        if attr in ("ver", "fam") and not ver:
                            ver = val
                        elif attr == "name":
                            name = val
            except Exception:
                pass

    clean = ver.replace("Lenovo ", "").replace("Legion ", "").strip()
    if not clean:
        clean = name or "Lenovo Legion"
    _CACHED_SYSTEM_MODEL = clean
    return clean


def get_memory_hardware_info() -> Dict[str, Any]:
    """
    Dynamically inspects SMBIOS Type 17 Memory Device entries (/sys/firmware/dmi/entries/17-*/raw)
    to extract populated DIMM count, per-DIMM capacity, DDR generation, speed (MT/s), and vendor.
    Falls back gracefully when SMBIOS entries are not world-readable.
    """
    global _CACHED_MEMORY_HARDWARE
    if _CACHED_MEMORY_HARDWARE is not None:
        return _CACHED_MEMORY_HARDWARE

    mem_type_map = {
        0x18: "DDR3",
        0x1A: "DDR4",
        0x1E: "LPDDR4",
        0x22: "DDR5",
        0x23: "LPDDR5",
    }

    dimms: List[Dict[str, Any]] = []
    for raw_path in sorted(glob.glob("/sys/firmware/dmi/entries/17-*/raw")):
        if not os.access(raw_path, os.R_OK):
            continue
        try:
            with open(raw_path, "rb") as f:
                data = f.read()
            if len(data) < 0x18:
                continue
            hdr_len = data[1]
            size_raw = struct.unpack("<H", data[0x0C:0x0E])[0]
            if size_raw == 0 or size_raw == 0xFFFF:
                continue
            if size_raw == 0x7FFF and hdr_len >= 0x20 and len(data) >= 0x20:
                ext_mb = struct.unpack("<I", data[0x1C:0x20])[0] & 0x7FFFFFFF
                size_gb = max(1, int(round(ext_mb / 1024.0)))
            else:
                if size_raw & 0x8000:
                    size_gb = max(1, int(round((size_raw & 0x7FFF) / (1024 * 1024))))
                else:
                    size_gb = max(1, int(round(size_raw / 1024.0)))

            mtype_code = data[0x12]
            mem_type = mem_type_map.get(mtype_code, "DDR5")
            speed_mts = struct.unpack("<H", data[0x15:0x17])[0]
            conf_speed = struct.unpack("<H", data[0x20:0x22])[0] if (hdr_len >= 0x22 and len(data) >= 0x22) else 0
            eff_speed = conf_speed or speed_mts

            raw_strs = [s.decode("utf-8", errors="replace").strip() for s in data[hdr_len:].split(b"\x00") if s.strip()]
            vendor = ""
            for s in raw_strs:
                sl = s.lower()
                if any(v in sl for v in ("micron", "samsung", "hynix", "sk hynix", "kingston", "crucial", "corsair", "g.skill")):
                    vendor = s.replace(" Technology", "").replace(" Semiconductor", "").strip()
                    break

            dimms.append({
                "size_gb": size_gb,
                "type": mem_type,
                "speed_mts": eff_speed,
                "vendor": vendor,
            })
        except Exception:
            pass

    spd_count = len(get_hwmons_by_name("spd5118"))
    if dimms:
        d0 = dimms[0]
        count = len(dimms)
        mtype = d0["type"]
        speed = d0["speed_mts"]
        size_gb = d0["size_gb"]
        vendor = d0["vendor"]
        type_speed = f"{mtype}-{speed}" if speed > 0 else mtype
        slot_summary = f"{count}x{size_gb}GB"
        summary = f"{type_speed} ({slot_summary} {vendor})".strip() if vendor else f"{type_speed} ({slot_summary})"
        short_summary = f"{type_speed} ({slot_summary})"
    else:
        mtype = "DDR5" if spd_count > 0 else "RAM"
        count = spd_count if spd_count > 0 else 0
        type_speed = mtype
        slot_summary = f"{count}x SODIMM" if count > 0 else "SODIMM"
        summary = f"{type_speed} ({slot_summary})"
        short_summary = summary

    _CACHED_MEMORY_HARDWARE = {
        "type": mtype,
        "speed_mts": dimms[0]["speed_mts"] if dimms else None,
        "dimm_count": len(dimms) if dimms else count,
        "dimm_size_gb": dimms[0]["size_gb"] if dimms else None,
        "vendor": dimms[0]["vendor"] if dimms else "",
        "type_speed": type_speed,
        "slot_summary": slot_summary,
        "summary": summary,
        "short_summary": short_summary,
    }
    return _CACHED_MEMORY_HARDWARE


_CACHED_NVME_META: Optional[List[Dict[str, Any]]] = None
_CACHED_NVME_DRIVES: Optional[List[Dict[str, Any]]] = None
_CACHED_NVME_TIME: float = 0.0
_CACHED_SPD_TEMPS: Optional[List[float]] = None
_CACHED_SPD_TIME: float = 0.0
_CACHED_BATTERY_INFO: Optional[Dict[str, Any]] = None
_CACHED_BATTERY_TIME: float = 0.0


def get_nvme_drives(ttl: float = 0.0) -> List[Dict[str, Any]]:
    """
    Reads per-drive NVMe telemetry (device name, model, capacity, PCIe link speed/width, temperatures).
    Caches static drive metadata and hwmon paths, and supports optional TTL caching so watch-mode loops
    avoid waking NVMe controllers via admin SMART log commands on every sub-second tick.
    """
    global _CACHED_NVME_META, _CACHED_NVME_DRIVES, _CACHED_NVME_TIME
    now = time.monotonic()
    if ttl > 0.0 and _CACHED_NVME_DRIVES is not None and (now - _CACHED_NVME_TIME) < ttl:
        return _CACHED_NVME_DRIVES

    if _CACHED_NVME_META is None:
        meta_list: List[Dict[str, Any]] = []
        for nvme_dir in sorted(glob.glob("/sys/class/nvme/nvme[0-9]*")):
            dev_name = os.path.basename(nvme_dir)
            model = dev_name.upper()
            model_p = os.path.join(nvme_dir, "model")
            if os.path.isfile(model_p):
                try:
                    with open(model_p, "r") as mf:
                        raw_m = " ".join(mf.read().strip().split())
                        if raw_m:
                            model = raw_m
                except Exception:
                    pass
            short_model = (
                model.replace("Samsung SSD ", "")
                .replace("Western Digital ", "WD ")
                .replace("WD_BLACK ", "WD ")
                .replace("KINGSTON ", "Kingston ")
                .strip()
            )

            pcie_tag = ""
            dev_link = os.path.realpath(os.path.join(nvme_dir, "device"))
            spd_p = os.path.join(dev_link, "current_link_speed")
            wid_p = os.path.join(dev_link, "current_link_width")
            if os.path.isfile(spd_p) and os.path.isfile(wid_p):
                try:
                    raw_spd = open(spd_p).read().strip()
                    raw_wid = open(wid_p).read().strip()
                    if "32.0" in raw_spd:
                        gen = "Gen5"
                    elif "16.0" in raw_spd:
                        gen = "Gen4"
                    elif "8.0" in raw_spd:
                        gen = "Gen3"
                    else:
                        gen = "PCIe"
                    pcie_tag = f"{gen} x{raw_wid}"
                except Exception:
                    pass

            if not any(u in short_model.upper() for u in ("TB", "GB")):
                ns_dirs = sorted(glob.glob(os.path.join(nvme_dir, f"{dev_name}n*")))
                if ns_dirs and os.path.isfile(os.path.join(ns_dirs[0], "size")):
                    try:
                        sectors = int(open(os.path.join(ns_dirs[0], "size")).read().strip())
                        gb = (sectors * 512) / 1e9
                        size_tag = f"{gb / 1000.0:.0f}TB" if gb >= 950 else f"{gb:.0f}GB"
                        short_model = f"{short_model} {size_tag}"
                    except Exception:
                        pass

            temp1_node: Optional[str] = None
            for hdir in sorted(glob.glob(os.path.join(nvme_dir, "hwmon*"))):
                tp = os.path.join(hdir, "temp1_input")
                if os.path.isfile(tp):
                    temp1_node = tp
                    break
            if temp1_node:
                meta_list.append({
                    "device": dev_name,
                    "model": model,
                    "short_model": short_model,
                    "pcie_tag": pcie_tag,
                    "temp1_node": temp1_node,
                })
        _CACHED_NVME_META = meta_list

    drives: List[Dict[str, Any]] = []
    for m in _CACHED_NVME_META:
        comp_c: Optional[float] = None
        try:
            with open(m["temp1_node"], "r") as tf:
                comp_c = round(int(tf.read().strip()) / 1000.0, 1)
        except Exception:
            pass
        if comp_c is not None:
            drives.append({
                "device": m["device"],
                "model": m["model"],
                "short_model": m["short_model"],
                "pcie_tag": m["pcie_tag"],
                "composite_c": comp_c,
            })
    _CACHED_NVME_DRIVES = drives
    _CACHED_NVME_TIME = now
    return drives


def get_nvme_temps() -> List[float]:
    """Reads composite NVMe drive temperatures in degrees Celsius."""
    drives = get_nvme_drives()
    if drives:
        return [d["composite_c"] for d in drives if d.get("composite_c") is not None]
    temps: List[float] = []
    for hdir in get_hwmons_by_name("nvme"):
        temp_file = os.path.join(hdir, "temp1_input")
        if os.path.isfile(temp_file):
            try:
                with open(temp_file, "r") as tf:
                    temps.append(round(int(tf.read().strip()) / 1000.0, 1))
            except Exception:
                pass
    return temps


def get_cpu_package_temp() -> Optional[float]:
    """Reads CPU Package temperature from coretemp (Intel) or k10temp/zenpower (AMD) hwmon."""
    for drv in ("coretemp", "k10temp", "zenpower", "acpitz"):
        ct_dir = get_hwmon_by_name(drv)
        if ct_dir:
            t_file = os.path.join(ct_dir, "temp1_input")
            if os.path.isfile(t_file):
                try:
                    with open(t_file, "r") as f:
                        return round(int(f.read().strip()) / 1000.0, 1)
                except Exception:
                    pass
    return None


def get_battery_info(ttl: float = 0.0) -> Dict[str, Any]:
    """Reads comprehensive battery telemetry, health, cycles, and conservation mode (with optional TTL cache to avoid 65ms ACPI EC stalls)."""
    global _CACHED_BATTERY_INFO, _CACHED_BATTERY_TIME
    now = time.monotonic()
    if ttl > 0.0 and _CACHED_BATTERY_INFO is not None and (now - _CACHED_BATTERY_TIME) < ttl:
        # Always refresh conservation_mode (<0.15ms) so interactive [c] toggle reflects immediately
        cons_active, _ = get_conservation_mode()
        _CACHED_BATTERY_INFO["conservation_mode"] = cons_active
        return dict(_CACHED_BATTERY_INFO)

    res = {
        "present": False,
        "capacity_percent": None,
        "status": "Unknown",
        "health_percent": None,
        "cycle_count": None,
        "voltage_v": None,
        "power_w": None,
        "conservation_mode": False,
    }

    if os.path.isdir(BATTERY_DIR):
        res["present"] = True
        try:
            for node, key, cast in [
                ("capacity", "capacity_percent", int),
                ("status", "status", str),
                ("cycle_count", "cycle_count", int),
            ]:
                p = os.path.join(BATTERY_DIR, node)
                if os.path.isfile(p):
                    with open(p, "r") as f:
                        res[key] = cast(f.read().strip())

            # Health
            ef_f = os.path.join(BATTERY_DIR, "energy_full")
            efd_f = os.path.join(BATTERY_DIR, "energy_full_design")
            if os.path.isfile(ef_f) and os.path.isfile(efd_f):
                with open(ef_f, "r") as f1, open(efd_f, "r") as f2:
                    ef = int(f1.read().strip())
                    efd = int(f2.read().strip())
                    if efd > 0:
                        res["health_percent"] = round((ef / efd) * 100.0, 1)

            # Voltage (uV -> V)
            v_f = os.path.join(BATTERY_DIR, "voltage_now")
            if os.path.isfile(v_f):
                with open(v_f, "r") as f:
                    res["voltage_v"] = round(int(f.read().strip()) / 1e6, 2)

            # Power draw (uW -> W)
            p_f = os.path.join(BATTERY_DIR, "power_now")
            if os.path.isfile(p_f):
                with open(p_f, "r") as f:
                    res["power_w"] = round(int(f.read().strip()) / 1e6, 2)
        except Exception:
            pass

    cons_active, _ = get_conservation_mode()
    res["conservation_mode"] = cons_active
    _CACHED_BATTERY_INFO = res
    _CACHED_BATTERY_TIME = now
    return dict(res)


_CACHED_DAEMON_PID: Optional[int] = None


def _read_daemon_rss_if_alive(pid: int) -> Optional[Tuple[int, Optional[float]]]:
    """Verifies pid belongs to a live legion-profile-osd process and returns (pid, rss_mib)."""
    try:
        with open(f"/proc/{pid}/stat", "r") as sf:
            st = sf.read()
        rparen = st.rfind(")")
        if rparen != -1 and len(st) > rparen + 2 and st[rparen + 2] == "Z":
            return None
        with open(f"/proc/{pid}/cmdline", "rb") as cf:
            cmd = cf.read().decode("utf-8", errors="ignore")
        if "legion-profile-osd" not in cmd:
            return None
        rss_mib = None
        with open(f"/proc/{pid}/status", "r") as status_f:
            for line in status_f:
                if line.startswith("VmRSS:"):
                    rss_mib = round(int(line.split()[1]) / 1024.0, 1)
                    break
        return pid, rss_mib
    except Exception:
        return None


def get_daemon_status() -> Dict[str, Any]:
    """Checks legion-profile-osd systemd user service status with fast procfs caching."""
    global _CACHED_DAEMON_PID
    res = {"active": False, "pid": None, "rss_mib": None}

    if _CACHED_DAEMON_PID is not None:
        alive = _read_daemon_rss_if_alive(_CACHED_DAEMON_PID)
        if alive is not None:
            res["active"] = True
            res["pid"], res["rss_mib"] = alive
            return res
        _CACHED_DAEMON_PID = None

    try:
        pid_proc = subprocess.run(
            ["systemctl", "--user", "show", "-p", "MainPID", "-p", "ActiveState", "--value", "legion-profile-osd.service"],
            capture_output=True, text=True, timeout=0.5
        )
        lines = [l.strip() for l in pid_proc.stdout.splitlines() if l.strip()]
        if len(lines) >= 2:
            # systemctl show outputs properties in unit definition order: MainPID then ActiveState (or vice versa)
            pid_str = next((x for x in lines if x.isdigit()), "0")
            is_act = "active" in lines
            if is_act and pid_str.isdigit() and int(pid_str) > 0:
                alive = _read_daemon_rss_if_alive(int(pid_str))
                if alive is not None:
                    _CACHED_DAEMON_PID = alive[0]
                    res["active"] = True
                    res["pid"], res["rss_mib"] = alive
                    return res
    except Exception:
        pass
    return res


_NVIDIA_RUNTIME_STATUS_NODE: Optional[str] = None


def is_nvidia_gpu_suspended() -> bool:
    """Checks sysfs to determine if the discrete NVIDIA GPU is in PCIe runtime suspend (D3cold)."""
    global _NVIDIA_RUNTIME_STATUS_NODE
    if _NVIDIA_RUNTIME_STATUS_NODE and os.path.isfile(_NVIDIA_RUNTIME_STATUS_NODE):
        try:
            with open(_NVIDIA_RUNTIME_STATUS_NODE, "r") as sf:
                return sf.read().strip().lower() in ("suspended", "suspending")
        except Exception:
            _NVIDIA_RUNTIME_STATUS_NODE = None

    for v_path in glob.glob("/sys/bus/pci/devices/*/vendor"):
        try:
            with open(v_path, "r") as f:
                if f.read().strip().lower() == "0x10de":
                    dev_dir = os.path.dirname(v_path)
                    cl_path = os.path.join(dev_dir, "class")
                    with open(cl_path, "r") as cf:
                        if cf.read().strip().startswith("0x03"):
                            st_path = os.path.join(dev_dir, "power", "runtime_status")
                            if os.path.isfile(st_path):
                                _NVIDIA_RUNTIME_STATUS_NODE = st_path
                                with open(st_path, "r") as sf:
                                    return sf.read().strip().lower() in ("suspended", "suspending")
        except Exception:
            pass
    return False


def _save_gpu_cache(data: Dict[str, Any]):
    """Caches dynamic GPU hardware specs to user cache directory."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(GPU_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_gpu_cache() -> Dict[str, Any]:
    """Loads cached dynamic GPU hardware specs if available."""
    if os.path.isfile(GPU_CACHE_FILE):
        try:
            with open(GPU_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _probe_nvidia_procfs() -> Dict[str, Any]:
    """
    Dynamically probes NVIDIA model, GPU firmware, and driver version from procfs
    without waking the PCIe device from D3cold.
    """
    info = {"name": "NVIDIA GPU", "driver": "N/A", "firmware": ""}
    for p in glob.glob("/proc/driver/nvidia/gpus/*/information"):
        try:
            with open(p, "r") as f:
                for line in f:
                    if line.startswith("Model:"):
                        info["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("GPU Firmware:"):
                        info["firmware"] = line.split(":", 1)[1].strip()
        except Exception:
            pass
        if info["name"] != "NVIDIA GPU":
            break

    v_path = "/proc/driver/nvidia/version"
    if os.path.isfile(v_path):
        try:
            with open(v_path, "r") as f:
                content = f.read()
                m = re.search(r"\b([0-9]{3}\.[0-9]{2}(?:\.[0-9]+)?)\b", content)
                if m:
                    info["driver"] = m.group(1)
        except Exception:
            pass
    if not info["firmware"] and info["driver"] != "N/A":
        info["firmware"] = info["driver"]
    return info


class _PerfEventAttr(ctypes.Structure):
    """Linux perf_event_attr structure for zero-overhead i915/xe PMU engine counters."""
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("config", ctypes.c_uint64),
        ("sample_period", ctypes.c_uint64),
        ("sample_type", ctypes.c_uint64),
        ("read_format", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
        ("wakeup_events", ctypes.c_uint32),
        ("bp_type", ctypes.c_uint32),
        ("config1", ctypes.c_uint64),
        ("config2", ctypes.c_uint64),
        ("branch_sample_type", ctypes.c_uint64),
        ("sample_regs_user", ctypes.c_uint64),
        ("sample_stack_user", ctypes.c_uint32),
        ("clockid", ctypes.c_int32),
        ("sample_regs_intr", ctypes.c_uint64),
        ("aux_watermark", ctypes.c_uint32),
        ("sample_max_stack", ctypes.c_uint16),
        ("__reserved_2", ctypes.c_uint16),
        ("aux_sample_size", ctypes.c_uint32),
        ("__reserved_3", ctypes.c_uint32),
    ]


class IntelIgpuTelemetry:
    """
    Zero-overhead integrated GPU telemetry via kernel PMU & sysfs (Intel i915/xe DRM & RAPL PP1, or AMD amdgpu).
    - Reads true hardware engine busyness (Render/3D rcs0, Compute ccs0, Video vcs0, Copy bcs0) in <5µs
      via Linux perf_event_open() on the i915 PMU (same source as intel_gpu_top), avoiding false 90-100%
      readings from display-wake RC6 counters.
    - Tracks live actual/max GT frequency (MHz) and PP1 uncore/iGPU power draw (Watts).
    """

    def __init__(self):
        self.card_dir: Optional[str] = None
        self.vendor: str = "Intel"
        self.name: str = "Intel Graphics"
        self.gt_dir: Optional[str] = None
        self.act_freq_node: Optional[str] = None
        self.cur_freq_node: Optional[str] = None
        self.max_freq_node: Optional[str] = None
        self.rc6_node: Optional[str] = None
        self.amd_busy_node: Optional[str] = None
        self.rapl_pp1_node: Optional[str] = "/sys/class/powercap/intel-rapl:0:1/energy_uj"
        self._pmu_fds: Dict[str, int] = {}
        self._last_pmu_ns: Dict[str, int] = {}
        self._last_pmu_time: Optional[float] = None
        self._last_rc6_ms: Optional[int] = None
        self._last_rc6_time: Optional[float] = None
        self._last_pp1_uj: Optional[int] = None
        self._last_pp1_time: Optional[float] = None

        for cdir in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
            if "-" in os.path.basename(cdir):
                continue
            vend_p = os.path.join(cdir, "device", "vendor")
            if os.path.isfile(vend_p):
                try:
                    with open(vend_p, "r") as vf:
                        vid = vf.read().strip().lower()
                        if vid == "0x8086":
                            self.card_dir = cdir
                            self.vendor = "Intel"
                            self.name = "Intel Graphics"
                            break
                        elif vid == "0x1002":
                            self.card_dir = cdir
                            self.vendor = "AMD"
                            self.name = "Radeon Graphics"
                except Exception:
                    pass

        if self.card_dir:
            if self.vendor == "Intel":
                gt0 = os.path.join(self.card_dir, "gt", "gt0")
                if os.path.isdir(gt0):
                    self.gt_dir = gt0
                    self.act_freq_node = os.path.join(gt0, "rps_act_freq_mhz")
                    self.cur_freq_node = os.path.join(gt0, "rps_cur_freq_mhz")
                    self.max_freq_node = os.path.join(gt0, "rps_max_freq_mhz")
                    self.rc6_node = os.path.join(gt0, "rc6_residency_ms")
                else:
                    self.act_freq_node = os.path.join(self.card_dir, "gt_act_freq_mhz")
                    self.cur_freq_node = os.path.join(self.card_dir, "gt_cur_freq_mhz")
                    self.max_freq_node = os.path.join(self.card_dir, "gt_max_freq_mhz")
                    self.rc6_node = os.path.join(self.card_dir, "power", "rc6_residency_ms")
                self._init_i915_pmu()
            else:
                self.amd_busy_node = os.path.join(self.card_dir, "device", "gpu_busy_percent")

        # Prime counters
        now = time.monotonic()
        if self._pmu_fds:
            self._last_pmu_ns = self._read_pmu_ns()
            self._last_pmu_time = now
        elif self.rc6_node and os.path.isfile(self.rc6_node):
            try:
                with open(self.rc6_node, "r") as f:
                    self._last_rc6_ms = int(f.read().strip())
                self._last_rc6_time = now
            except Exception:
                pass
        if self.rapl_pp1_node and os.path.isfile(self.rapl_pp1_node):
            try:
                with open(self.rapl_pp1_node, "r") as f:
                    self._last_pp1_uj = int(f.read().strip())
                self._last_pp1_time = now
            except Exception:
                pass

    def _init_i915_pmu(self):
        """Opens direct kernel perf_event descriptors for i915 engine busyness counters."""
        pmu_type_path = "/sys/bus/event_source/devices/i915/type"
        if not os.path.isfile(pmu_type_path):
            return
        try:
            with open(pmu_type_path, "r") as f:
                pmu_type = int(f.read().strip())
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            sys_perf_event_open = 298  # x86_64 __NR_perf_event_open
            # Engine busy configs from /sys/bus/event_source/devices/i915/events/*-busy
            engines = [("rcs0", 0x0), ("bcs0", 0x1000), ("vcs0", 0x2000), ("ccs0", 0x4000)]
            for eng_name, cfg in engines:
                attr = _PerfEventAttr()
                attr.type = pmu_type
                attr.size = ctypes.sizeof(_PerfEventAttr)
                attr.config = cfg
                fd = libc.syscall(sys_perf_event_open, ctypes.byref(attr), -1, 0, -1, 0)
                if fd >= 0:
                    self._pmu_fds[eng_name] = int(fd)
        except Exception:
            pass

    def _read_pmu_ns(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for eng, fd in self._pmu_fds.items():
            try:
                raw = os.read(fd, 8)
                if len(raw) == 8:
                    out[eng] = struct.unpack("<Q", raw)[0]
            except Exception:
                pass
        return out

    def query(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "available": self.card_dir is not None,
            "vendor": self.vendor,
            "name": self.name,
            "clock_mhz": None,
            "max_clock_mhz": 1900 if self.vendor == "Intel" else None,
            "utilization_pct": 0.0,
            "power_draw_w": None,
        }
        if not self.card_dir:
            return res

        now = time.monotonic()
        if self.amd_busy_node and os.path.isfile(self.amd_busy_node):
            try:
                with open(self.amd_busy_node, "r") as f:
                    res["utilization_pct"] = float(f.read().strip())
            except Exception:
                pass

        for node, key in ((self.act_freq_node, "clock_mhz"), (self.max_freq_node, "max_clock_mhz")):
            if node and os.path.isfile(node):
                try:
                    with open(node, "r") as f:
                        res[key] = int(f.read().strip())
                except Exception:
                    pass
        if not res["clock_mhz"] and self.cur_freq_node and os.path.isfile(self.cur_freq_node):
            try:
                with open(self.cur_freq_node, "r") as f:
                    res["clock_mhz"] = int(f.read().strip())
            except Exception:
                pass

        # 1. Primary: Exact kernel PMU engine busyness (Render/Compute/Video/Copy)
        # Scale time-active busyness by (clock_mhz / max_clock_mhz) so execution at base clock
        # (e.g. 60% time active at 550 MHz out of 1900 MHz) reports true hardware capacity load (~17%)
        # rather than alarming 60-90% idle time-active figures during multi-GPU display blits.
        cur_clk = res.get("clock_mhz") or 550
        max_clk = res.get("max_clock_mhz") or 1900
        freq_scale = min(1.0, max(0.25, cur_clk / max(1, max_clk)))
        if self._pmu_fds:
            cur_ns = self._read_pmu_ns()
            if self._last_pmu_ns and self._last_pmu_time is not None:
                dt_ns = (now - self._last_pmu_time) * 1e9
                if dt_ns >= 1e7:  # >= 10ms window
                    max_eng_pct = 0.0
                    for eng, val_now in cur_ns.items():
                        val_prev = self._last_pmu_ns.get(eng)
                        if val_prev is not None and val_now >= val_prev:
                            pct = min(100.0, max(0.0, ((val_now - val_prev) / dt_ns) * 100.0))
                            if pct > max_eng_pct:
                                max_eng_pct = pct
                    res["engine_busy_pct"] = round(max_eng_pct, 1)
                    res["utilization_pct"] = round(min(100.0, max_eng_pct * freq_scale), 1)
                    self._last_pmu_ns = cur_ns
                    self._last_pmu_time = now
            else:
                self._last_pmu_ns = cur_ns
                self._last_pmu_time = now
        # 2. Fallback: RC6 residency counter if PMU is unavailable
        elif self.rc6_node and os.path.isfile(self.rc6_node):
            try:
                with open(self.rc6_node, "r") as f:
                    rc6_now = int(f.read().strip())
                if self._last_rc6_ms is not None and self._last_rc6_time is not None:
                    dt_ms = (now - self._last_rc6_time) * 1000.0
                    d_rc6 = rc6_now - self._last_rc6_ms
                    if dt_ms >= 200.0 and d_rc6 >= 0:
                        busy = max(0.0, min(100.0, (1.0 - (d_rc6 / dt_ms)) * 100.0))
                        res["engine_busy_pct"] = round(busy, 1)
                        res["utilization_pct"] = round(min(100.0, busy * freq_scale), 1)
                        self._last_rc6_ms = rc6_now
                        self._last_rc6_time = now
                else:
                    self._last_rc6_ms = rc6_now
                    self._last_rc6_time = now
            except Exception:
                pass

        if self.rapl_pp1_node and os.path.isfile(self.rapl_pp1_node):
            try:
                with open(self.rapl_pp1_node, "r") as f:
                    pp1_now = int(f.read().strip())
                if self._last_pp1_uj is not None and self._last_pp1_time is not None:
                    dt = now - self._last_pp1_time
                    de = pp1_now - self._last_pp1_uj
                    if dt >= 0.015 and de >= 0:
                        res["power_draw_w"] = round(de / (dt * 1e6), 1)
                self._last_pp1_uj = pp1_now
                self._last_pp1_time = now
            except Exception:
                pass

        return res

    def close(self):
        """Closes open perf_event PMU file descriptors."""
        for fd in self._pmu_fds.values():
            try:
                os.close(fd)
            except Exception:
                pass
        self._pmu_fds.clear()


# --- Native NVML Engine via ctypes ---

_CACHED_NVIDIA_DRM_INFO: Optional[Dict[str, str]] = None


def _get_nvidia_drm_info() -> Dict[str, str]:
    """
    Dynamically discovers the NVIDIA DRM card (vendor 0x10de), its connector status glob,
    and its DRM render node (e.g. /dev/dri/renderD129) without waking the GPU.
    """
    global _CACHED_NVIDIA_DRM_INFO
    if _CACHED_NVIDIA_DRM_INFO is not None:
        return _CACHED_NVIDIA_DRM_INFO

    info = {
        "card_name": "card0",
        "connector_glob": "/sys/class/drm/card0-*/status",
        "render_node": "/dev/dri/renderD129",
    }
    for cdir in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        cbase = os.path.basename(cdir)
        if "-" in cbase:
            continue
        vend_p = os.path.join(cdir, "device", "vendor")
        if os.path.isfile(vend_p):
            try:
                with open(vend_p, "r") as vf:
                    if vf.read().strip().lower() == "0x10de":
                        render_nodes = sorted(glob.glob(os.path.join(cdir, "device", "drm", "renderD*")))
                        rnode = f"/dev/dri/{os.path.basename(render_nodes[0])}" if render_nodes else "/dev/dri/renderD129"
                        info = {
                            "card_name": cbase,
                            "connector_glob": f"/sys/class/drm/{cbase}-*/status",
                            "render_node": rnode,
                        }
                        break
            except Exception:
                pass
    _CACHED_NVIDIA_DRM_INFO = info
    return info


def is_nvidia_idle_with_no_outputs() -> bool:
    """
    Returns True if all NVIDIA DRM display connectors are disconnected.
    """
    c_glob = _get_nvidia_drm_info()["connector_glob"]
    for st_path in glob.glob(c_glob):
        try:
            with open(st_path, "r") as f:
                if f.read().strip().lower() == "connected":
                    return False
        except Exception:
            pass
    return True


_NVIDIA_FD_IGNORE_COMMS = frozenset({
    "lstats", "lstats-nvml", "kwin_wayland", "kwin_wayland_wr",
    "Xwayland", "Xorg", "legion-profile-",
})


def has_active_nvidia_user_client() -> bool:
    """
    Passively scans user-owned /proc/<pid>/fd symlinks for active compute/3D applications
    holding NVIDIA device nodes (/dev/nvidia[0-9]*, /dev/nvidia-uvm, or NVIDIA renderD* node)
    without opening any NVIDIA device node or waking D3cold sleep.
    """
    my_uid = os.getuid()
    my_pid = str(os.getpid())
    render_node = _get_nvidia_drm_info()["render_node"]

    for proc_dir in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(proc_dir)
        if pid == my_pid:
            continue
        try:
            if os.stat(proc_dir).st_uid != my_uid:
                continue
            with open(os.path.join(proc_dir, "comm"), "r") as cf:
                comm = cf.read().strip()
            if comm in _NVIDIA_FD_IGNORE_COMMS:
                continue
            fd_dir = os.path.join(proc_dir, "fd")
            for fd_name in os.listdir(fd_dir):
                try:
                    t = os.readlink(os.path.join(fd_dir, fd_name))
                    if t == render_node or t == "/dev/nvidia-uvm":
                        return True
                    if t.startswith("/dev/nvidia") and len(t) > 11 and t[11].isdigit():
                        return True
                except Exception:
                    pass
        except Exception:
            pass
    return False


_NVML_IGNORE_COMMS = frozenset({"kwin_wayland", "kwin_wayland_wr", "Xorg", "Xwayland"})


def _nvml_worker_main(cmd_r: int, res_w: int) -> None:
    """
    Isolated NVML worker loop running inside a forked child process.
    Keeps libnvidia-ml.so and its internal CUDA worker thread completely out of the parent
    process so stopping this child guarantees every /dev/nvidia* fd and thread is torn down,
    allowing the kernel PCIe runtime PM governor to transition the dGPU into D3cold sleep.
    """
    nvml = None
    nvml_ok = False
    dev = ctypes.c_void_p()

    try:
        try:
            libc = ctypes.CDLL("libc.so.6")
            libc.prctl(1, signal.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG
            libc.prctl(15, b"lstats-nvml", 0, 0, 0)  # PR_SET_NAME
        except Exception:
            pass

        try:
            devnull_fd = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull_fd, 0)
            os.dup2(devnull_fd, 1)
            os.dup2(devnull_fd, 2)
            if devnull_fd > 2:
                os.close(devnull_fd)
        except Exception:
            pass

        # Close inherited non-essential descriptors from parent
        try:
            for fd_str in os.listdir("/proc/self/fd"):
                try:
                    fd_num = int(fd_str)
                    if fd_num > 2 and fd_num not in (cmd_r, res_w):
                        os.close(fd_num)
                except Exception:
                    pass
        except Exception:
            pass

        class _NvmlMemory(ctypes.Structure):
            _fields_ = [
                ("total", ctypes.c_ulonglong),
                ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong),
            ]

        class _NvmlUtilization(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        class _NvmlProcInfo(ctypes.Structure):
            _fields_ = [
                ("pid", ctypes.c_uint),
                ("usedGpuMemory", ctypes.c_ulonglong),
                ("gpuInstanceId", ctypes.c_uint),
                ("computeInstanceId", ctypes.c_uint),
            ]

        nvml = ctypes.CDLL("libnvidia-ml.so.1")
        if nvml.nvmlInit() == 0:
            nvml_ok = True
            if nvml.nvmlDeviceGetHandleByIndex(0, ctypes.byref(dev)) != 0:
                dev = None
        else:
            dev = None

        spec_name = "NVIDIA GPU"
        spec_driver = "N/A"
        spec_mem_tot: Optional[int] = None
        spec_plim: Optional[float] = None

        if nvml_ok and dev:
            name_buf = ctypes.create_string_buffer(64)
            if nvml.nvmlDeviceGetName(dev, name_buf, 64) == 0:
                spec_name = name_buf.value.decode("utf-8", errors="replace")

            drv_buf = ctypes.create_string_buffer(64)
            if nvml.nvmlSystemGetDriverVersion(drv_buf, 64) == 0:
                spec_driver = drv_buf.value.decode("utf-8", errors="replace")

            mem_s = _NvmlMemory()
            if nvml.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(mem_s)) == 0:
                spec_mem_tot = int(mem_s.total // (1024 * 1024))

            plim_s = ctypes.c_uint()
            if nvml.nvmlDeviceGetEnforcedPowerLimit(dev, ctypes.byref(plim_s)) == 0:
                spec_plim = round(plim_s.value / 1000.0, 1)

        proc_fns = []
        for fn_name in (
            "nvmlDeviceGetComputeRunningProcesses_v3",
            "nvmlDeviceGetGraphicsRunningProcesses_v3",
        ):
            fn = getattr(nvml, fn_name, None) if nvml else None
            if fn is not None:
                proc_fns.append(fn)
        if not proc_fns and nvml:
            for fn_name in (
                "nvmlDeviceGetComputeRunningProcesses_v2",
                "nvmlDeviceGetGraphicsRunningProcesses_v2",
                "nvmlDeviceGetComputeRunningProcesses",
                "nvmlDeviceGetGraphicsRunningProcesses",
            ):
                fn = getattr(nvml, fn_name, None)
                if fn is not None:
                    proc_fns.append(fn)

        cmd_file = os.fdopen(cmd_r, "r", encoding="utf-8", buffering=1)
        res_file = os.fdopen(res_w, "w", encoding="utf-8", buffering=1)

        for raw_cmd in cmd_file:
            cmd = raw_cmd.strip()
            if not cmd or cmd == "EXIT":
                break
            if cmd != "QUERY":
                continue

            res: Dict[str, Any] = {
                "name": spec_name,
                "driver": spec_driver,
                "temperature_c": None,
                "power_draw_w": None,
                "power_limit_w": spec_plim,
                "memory_used_mib": None,
                "memory_total_mib": spec_mem_tot,
                "memory_percent": 0.0,
                "utilization_gpu": None,
                "utilization_mem": None,
                "clock_graphics_mhz": None,
                "clock_memory_mhz": None,
                "has_active_app": False,
                "gpu_procs": {},
            }

            if nvml_ok and dev:
                try:
                    temp = ctypes.c_uint()
                    if nvml.nvmlDeviceGetTemperature(dev, 0, ctypes.byref(temp)) == 0:
                        res["temperature_c"] = int(temp.value)

                    power = ctypes.c_uint()
                    if nvml.nvmlDeviceGetPowerUsage(dev, ctypes.byref(power)) == 0:
                        res["power_draw_w"] = round(power.value / 1000.0, 1)

                    plimit = ctypes.c_uint()
                    if nvml.nvmlDeviceGetEnforcedPowerLimit(dev, ctypes.byref(plimit)) == 0:
                        res["power_limit_w"] = round(plimit.value / 1000.0, 1)

                    mem = _NvmlMemory()
                    if nvml.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(mem)) == 0:
                        res["memory_used_mib"] = int(mem.used // (1024 * 1024))
                        res["memory_total_mib"] = int(mem.total // (1024 * 1024))
                        if res["memory_total_mib"] > 0:
                            res["memory_percent"] = round((res["memory_used_mib"] / res["memory_total_mib"]) * 100.0, 1)

                    util = _NvmlUtilization()
                    if nvml.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util)) == 0:
                        res["utilization_gpu"] = int(util.gpu)
                        res["utilization_mem"] = int(util.memory)

                    clk_gfx = ctypes.c_uint()
                    if nvml.nvmlDeviceGetClockInfo(dev, 0, ctypes.byref(clk_gfx)) == 0:
                        res["clock_graphics_mhz"] = int(clk_gfx.value)
                    clk_mem = ctypes.c_uint()
                    if nvml.nvmlDeviceGetClockInfo(dev, 2, ctypes.byref(clk_mem)) == 0:
                        res["clock_memory_mhz"] = int(clk_mem.value)

                    # Collect per-PID VRAM usage (MiB) and detect non-compositor apps using dGPU
                    gpu_procs: Dict[str, int] = {}
                    for fn in proc_fns:
                        try:
                            cnt = ctypes.c_uint(64)
                            arr = (_NvmlProcInfo * 64)()
                            if fn(dev, ctypes.byref(cnt), arr) == 0:
                                for idx in range(min(cnt.value, 64)):
                                    p_id = int(arr[idx].pid)
                                    raw_mem = int(arr[idx].usedGpuMemory)
                                    # NVML returns 0xFFFFFFFFFFFFFFFF (NVML_VALUE_NOT_AVAILABLE) when unavailable
                                    mib = int(raw_mem // (1024 * 1024)) if raw_mem < (1 << 50) else 0
                                    pid_key = str(p_id)
                                    if mib > gpu_procs.get(pid_key, 0):
                                        gpu_procs[pid_key] = mib
                                    if not res["has_active_app"]:
                                        try:
                                            with open(f"/proc/{p_id}/comm", "r") as pf:
                                                p_comm = pf.read().strip()
                                            if p_comm not in _NVML_IGNORE_COMMS:
                                                res["has_active_app"] = True
                                        except Exception:
                                            # Unreadable /proc/<pid>/comm (e.g. another UID like ollama) -> active app
                                            res["has_active_app"] = True
                        except Exception:
                            pass
                    res["gpu_procs"] = gpu_procs
                except Exception:
                    pass

            res_file.write(json.dumps(res) + "\n")
            res_file.flush()
    except Exception:
        pass
    finally:
        if nvml and nvml_ok:
            try:
                nvml.nvmlShutdown()
            except Exception:
                pass
        os._exit(0)


class NvmlTelemetry:
    """Zero-overhead NVIDIA telemetry isolated in a forked NVML worker to preserve D3cold runtime PM."""

    def __init__(self, allow_wake: bool = False):
        self.available = False
        self.suspended = False
        self.name = "NVIDIA GPU"
        self.driver_version = "N/A"
        self.firmware = ""
        self.memory_total_mib: Optional[int] = None
        self.power_limit_w: Optional[float] = None
        self._allow_wake = allow_wake
        self._worker_pid: Optional[int] = None
        self._cmd_w: Optional[int] = None
        self._res_r: Optional[int] = None
        self._res_file = None
        self._idling = False
        self._idle_cooldown_until: float = 0.0
        self._idle_backoff_s: float = 20.0
        self._last_client_scan: float = 0.0

        proc_info = _probe_nvidia_procfs()
        cache = _load_gpu_cache()
        if cache and cache.get("name"):
            self.name = cache.get("name", self.name)
            self.driver_version = cache.get("driver", self.driver_version)
            self.firmware = cache.get("firmware") or proc_info.get("firmware") or ""
            self.memory_total_mib = cache.get("memory_total_mib")
            self.power_limit_w = cache.get("power_limit_w")
        else:
            self.name = proc_info.get("name", self.name)
            self.driver_version = proc_info.get("driver", self.driver_version)
            self.firmware = proc_info.get("firmware", "")
        if not self.firmware and self.driver_version != "N/A":
            self.firmware = self.driver_version

        if not allow_wake and is_nvidia_gpu_suspended():
            self.suspended = True
            return

        if not is_nvidia_idle_with_no_outputs():
            self._start_worker()

    def _start_worker(self) -> bool:
        """Spawns the isolated NVML child worker if not already running."""
        if self._worker_pid is not None:
            return True
        cmd_r = cmd_w = res_r = res_w = -1
        try:
            cmd_r, cmd_w = os.pipe()
            res_r, res_w = os.pipe()
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(cmd_w)
                    os.close(res_r)
                except Exception:
                    pass
                _nvml_worker_main(cmd_r, res_w)
                os._exit(0)
            os.close(cmd_r)
            os.close(res_w)
            self._worker_pid = pid
            self._cmd_w = cmd_w
            self._res_r = res_r
            self._res_file = os.fdopen(res_r, "r", encoding="utf-8", buffering=1)
            self.available = True
            return True
        except Exception:
            for fd in (cmd_r, cmd_w, res_r, res_w):
                if fd >= 0:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
            self._worker_pid = None
            self._cmd_w = None
            self._res_r = None
            self._res_file = None
            self.available = False
            return False

    def _stop_worker(self):
        """Cleanly terminates and reaps the forked NVML worker, tearing down libnvidia-ml completely."""
        pid = self._worker_pid
        cmd_w = self._cmd_w
        res_file = self._res_file
        res_r = self._res_r

        self._worker_pid = None
        self._cmd_w = None
        self._res_file = None
        self._res_r = None
        self.available = False

        if cmd_w is not None:
            try:
                os.write(cmd_w, b"EXIT\n")
            except Exception:
                pass
            try:
                os.close(cmd_w)
            except Exception:
                pass

        if res_file is not None:
            try:
                res_file.close()
            except Exception:
                pass
        elif res_r is not None:
            try:
                os.close(res_r)
            except Exception:
                pass

        if pid is not None:
            reaped = False
            for _ in range(25):
                try:
                    wpid, _ = os.waitpid(pid, os.WNOHANG)
                    if wpid == pid:
                        reaped = True
                        break
                except ChildProcessError:
                    reaped = True
                    break
                except Exception:
                    break
                time.sleep(0.02)
            if not reaped:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
                except Exception:
                    pass

    def _query_worker(self) -> Optional[Dict[str, Any]]:
        """Requests one NVML sample from the forked worker with a 4s timeout (covers cold D3cold resume)."""
        if self._worker_pid is None or self._cmd_w is None or self._res_file is None or self._res_r is None:
            return None
        try:
            os.write(self._cmd_w, b"QUERY\n")
            r_ready, _, _ = select.select([self._res_r], [], [], 4.0)
            if not r_ready:
                self._stop_worker()
                return None
            line = self._res_file.readline()
            if not line:
                self._stop_worker()
                return None
            data = json.loads(line)
            changed = False
            if data.get("name") and data["name"] != "NVIDIA GPU" and data["name"] != self.name:
                self.name = data["name"]
                changed = True
            if data.get("driver") and data["driver"] != "N/A" and data["driver"] != self.driver_version:
                self.driver_version = data["driver"]
                changed = True
            if not self.firmware and self.driver_version != "N/A":
                self.firmware = self.driver_version
                changed = True
            if data.get("memory_total_mib") and data["memory_total_mib"] != self.memory_total_mib:
                self.memory_total_mib = data["memory_total_mib"]
                changed = True
            if data.get("power_limit_w") and data["power_limit_w"] != self.power_limit_w:
                self.power_limit_w = data["power_limit_w"]
                changed = True
            if changed:
                _save_gpu_cache({
                    "name": self.name,
                    "driver": self.driver_version,
                    "firmware": self.firmware,
                    "memory_total_mib": self.memory_total_mib,
                    "power_limit_w": self.power_limit_w,
                })
            return data
        except Exception:
            self._stop_worker()
            return None

    def _inactive_payload(self, state: str, power_draw_w: Optional[float]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "driver": self.driver_version,
            "firmware": self.firmware,
            "temperature_c": None,
            "power_draw_w": power_draw_w,
            "power_limit_w": self.power_limit_w,
            "memory_used_mib": 0,
            "memory_total_mib": self.memory_total_mib,
            "memory_percent": 0.0,
            "utilization_gpu": 0,
            "utilization_mem": 0,
            "clock_graphics_mhz": 0,
            "clock_memory_mhz": 0,
            "gpu_procs": {},
            "state": state,
        }

    def query(self) -> Dict[str, Any]:
        """Queries current GPU metrics while releasing NVML cleanly when idle so dGPU enters D3cold sleep."""
        now = time.monotonic()

        if not self._allow_wake and is_nvidia_gpu_suspended():
            self._stop_worker()
            self.suspended = True
            self._idling = False
            self._idle_cooldown_until = 0.0
            self._idle_backoff_s = 20.0
            return self._inactive_payload("suspended", 0.0)

        no_outputs = is_nvidia_idle_with_no_outputs()
        if not no_outputs:
            self._idling = False
            self._idle_cooldown_until = 0.0
            self._idle_backoff_s = 20.0

        # Passive idle backoff: keep worker shut down so PCIe RTD3 reaches D3cold undisturbed
        if not self._allow_wake and no_outputs and self._idling:
            if (now - self._last_client_scan) >= 2.0:
                self._last_client_scan = now
                if has_active_nvidia_user_client():
                    self._idling = False
                    self._idle_cooldown_until = 0.0
                    self._idle_backoff_s = 20.0
            if self._idling and now < self._idle_cooldown_until:
                self._stop_worker()
                return self._inactive_payload("idling", None)

        if self._worker_pid is None:
            if not self._start_worker():
                return {
                    "name": self.name,
                    "driver": self.driver_version,
                    "firmware": self.firmware,
                    "temperature_c": None,
                    "power_draw_w": None,
                    "power_limit_w": self.power_limit_w,
                    "memory_used_mib": None,
                    "memory_total_mib": self.memory_total_mib,
                    "memory_percent": 0.0,
                    "utilization_gpu": None,
                    "utilization_mem": None,
                    "clock_graphics_mhz": None,
                    "clock_memory_mhz": None,
                }

        res = self._query_worker()
        if res is None:
            return {
                "name": self.name,
                "driver": self.driver_version,
                "firmware": self.firmware,
                "temperature_c": None,
                "power_draw_w": None,
                "power_limit_w": self.power_limit_w,
                "memory_used_mib": None,
                "memory_total_mib": self.memory_total_mib,
                "memory_percent": 0.0,
                "utilization_gpu": None,
                "utilization_mem": None,
                "clock_graphics_mhz": None,
                "clock_memory_mhz": None,
            }

        self.suspended = False
        has_app = bool(res.pop("has_active_app", False))
        res["firmware"] = self.firmware or (res.get("driver") if res.get("driver") not in (None, "", "N/A") else "")

        if (
            not self._allow_wake
            and no_outputs
            and not has_app
            and (res.get("utilization_gpu") or 0) == 0
            and (res.get("memory_used_mib") or 0) < 900
        ):
            self._stop_worker()
            self._idling = True
            self._idle_cooldown_until = now + self._idle_backoff_s
            self._idle_backoff_s = min(120.0, self._idle_backoff_s * 2.0)
            self._last_client_scan = now
            return self._inactive_payload("idling", None)

        self._idling = False
        self._idle_cooldown_until = 0.0
        self._idle_backoff_s = 20.0
        res["state"] = "active"
        return res

    def close(self):
        """Terminates and reaps the forked NVML worker."""
        self._stop_worker()
