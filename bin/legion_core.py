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
import shutil
import ctypes
import subprocess
import re
from typing import Dict, Any, Optional, Tuple, List

# --- Hardware Paths & System Nodes ---

PLATFORM_PROFILE_NODE = "/sys/firmware/acpi/platform_profile"
PLATFORM_PROFILE_CHOICES_NODE = "/sys/firmware/acpi/platform_profile_choices"
CONSERVATION_MODE_NODE = "/sys/devices/pci0000:00/0000:00:1f.0/PNP0C09:00/VPC2004:00/conservation_mode"
BATTERY_DIR = "/sys/class/power_supply/BAT0"
RAPL_ENERGY_NODE = "/sys/class/powercap/intel-rapl:0/energy_uj"
HOTKEY_NODE = "/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event"

EXPECTED_PANEL_ID = "SDC420B"

CONFIG_DIR = os.path.expanduser("~/.config/legion")
CACHE_DIR = os.path.expanduser("~/.cache/legion")
GPU_CACHE_FILE = os.path.join(CACHE_DIR, "gpu_info.json")
ICON_DIR = os.path.expanduser("~/.local/share/icons/legion")
COLOR_PROFILE_DIR = os.path.expanduser("~/.local/share/color/icc")

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
    Ensures WAYLAND_DISPLAY, DISPLAY, and XDG session variables are set in os.environ.
    Essential when scripts/daemons are executed from minimal environments (systemd, udev, SSH).
    """
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        return

    uid = os.getuid()
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    os.environ["XDG_RUNTIME_DIR"] = runtime_dir

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
                        "XDG_SESSION_TYPE", "XAUTHORITY", "PATH", "QT_WAYLAND_RECONNECT"
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


def get_active_display_info() -> Dict[str, Any]:
    """
    Queries kscreen-doctor -j for the primary connected eDP output.
    Returns dictionary with:
      - output_name: str (e.g. 'eDP-1')
      - icc_profile_path: str
      - refresh_rate_hz: float (e.g. 60.0 or 240.0)
      - resolution: str (e.g. '2560x1600')
      - scale: float (e.g. 1.5)
    """
    ensure_gui_environment()
    res = {
        "output_name": "eDP-1",
        "icc_profile_path": "",
        "refresh_rate_hz": 240.0,
        "resolution": "2560x1600",
        "scale": 1.5,
    }
    if not shutil.which("kscreen-doctor"):
        return res

    try:
        proc = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=1)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            outputs = data.get("outputs", [])
            target = None
            for out in outputs:
                if out.get("connected") and out.get("enabled"):
                    name = out.get("name", "")
                    if name.startswith("eDP") or out.get("priority") == 1:
                        target = out
                        break
            if not target:
                for out in outputs:
                    if out.get("connected") and out.get("enabled"):
                        target = out
                        break

            if target:
                res["output_name"] = target.get("name", "eDP-1")
                res["icc_profile_path"] = target.get("iccProfilePath") or ""
                res["scale"] = float(target.get("scale", 1.5))

                curr_mode_id = str(target.get("currentModeId"))
                for m in target.get("modes", []):
                    if str(m.get("id")) == curr_mode_id:
                        res["refresh_rate_hz"] = round(float(m.get("refreshRate", 240)), 2)
                        size = m.get("size", {})
                        if "width" in size and "height" in size:
                            res["resolution"] = f"{size['width']}x{size['height']}"
                        break
    except Exception:
        pass

    # Fast regex fallback from kscreen-doctor -o if refresh rate is still unparsed
    if shutil.which("kscreen-doctor"):
        try:
            proc_o = subprocess.run(["kscreen-doctor", "-o"], capture_output=True, text=True, timeout=1)
            if proc_o.returncode == 0:
                m = re.search(r"@([0-9.]+)\*", proc_o.stdout)
                if m:
                    res["refresh_rate_hz"] = round(float(m.group(1)), 2)
        except Exception:
            pass

    return res


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


def get_hwmon_by_name(name: str) -> Optional[str]:
    """Finds the first sysfs hwmon directory matching the given device name."""
    for p in glob.glob("/sys/class/hwmon/hwmon*"):
        name_file = os.path.join(p, "name")
        if os.path.isfile(name_file):
            try:
                with open(name_file, "r") as f:
                    if f.read().strip() == name:
                        return p
            except Exception:
                pass
    return None


def get_cooling_fans() -> Dict[str, Any]:
    """
    Queries Lenovo triple-fan configuration via lenovo_wmi_other hwmon.
    CPU Fan (fan1), GPU Fan (fan2), Aux/Rear Fan (fan4).
    """
    res = {
        "cpu_fan": {"rpm": 0, "max_rpm": 5200, "percent": 0.0},
        "gpu_fan": {"rpm": 0, "max_rpm": 5400, "percent": 0.0},
        "aux_fan": {"rpm": 0, "max_rpm": 6500, "percent": 0.0},
    }

    wmi_dir = get_hwmon_by_name("lenovo_wmi_other")
    if wmi_dir:
        fan_mappings = [
            ("fan1", "cpu_fan", 5200),
            ("fan2", "gpu_fan", 5400),
            ("fan4", "aux_fan", 6500),
        ]
        for prefix, key, default_max in fan_mappings:
            inp = os.path.join(wmi_dir, f"{prefix}_input")
            max_f = os.path.join(wmi_dir, f"{prefix}_max")
            rpm = 0
            max_rpm = default_max

            if os.path.isfile(inp):
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
            res[key] = {"rpm": rpm, "max_rpm": max_rpm, "percent": pct}

    return res


def get_spd_ram_temps() -> List[float]:
    """Reads DDR5 SPD thermal sensors (spd5118) in degrees Celsius."""
    temps: List[float] = []
    for hdir in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name_file = os.path.join(hdir, "name")
        if os.path.isfile(name_file):
            try:
                with open(name_file, "r") as f:
                    if f.read().strip() == "spd5118":
                        temp_file = os.path.join(hdir, "temp1_input")
                        if os.path.isfile(temp_file):
                            with open(temp_file, "r") as tf:
                                temps.append(round(int(tf.read().strip()) / 1000.0, 1))
            except Exception:
                pass
    return temps


def get_nvme_temps() -> List[float]:
    """Reads composite NVMe drive temperatures in degrees Celsius."""
    temps: List[float] = []
    for hdir in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name_file = os.path.join(hdir, "name")
        if os.path.isfile(name_file):
            try:
                with open(name_file, "r") as f:
                    if f.read().strip() == "nvme":
                        temp_file = os.path.join(hdir, "temp1_input")
                        if os.path.isfile(temp_file):
                            with open(temp_file, "r") as tf:
                                temps.append(round(int(tf.read().strip()) / 1000.0, 1))
            except Exception:
                pass
    return temps


def get_cpu_package_temp() -> Optional[float]:
    """Reads CPU Package 0 temperature from coretemp hwmon."""
    ct_dir = get_hwmon_by_name("coretemp")
    if ct_dir:
        t_file = os.path.join(ct_dir, "temp1_input")
        if os.path.isfile(t_file):
            try:
                with open(t_file, "r") as f:
                    return round(int(f.read().strip()) / 1000.0, 1)
            except Exception:
                pass
    return None


def get_battery_info() -> Dict[str, Any]:
    """Reads comprehensive battery telemetry, health, cycles, and conservation mode."""
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
    return res


def get_daemon_status() -> Dict[str, Any]:
    """Checks legion-profile-osd systemd user service status."""
    res = {"active": False, "pid": None, "rss_mib": None}
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "legion-profile-osd.service"],
            capture_output=True, text=True, timeout=0.5
        )
        res["active"] = proc.stdout.strip() == "active"
        if res["active"]:
            pid_proc = subprocess.run(
                ["systemctl", "--user", "show", "-p", "MainPID", "--value", "legion-profile-osd.service"],
                capture_output=True, text=True, timeout=0.5
            )
            pid_str = pid_proc.stdout.strip()
            if pid_str.isdigit() and int(pid_str) > 0:
                pid = int(pid_str)
                res["pid"] = pid
                status_path = f"/proc/{pid}/status"
                if os.path.isfile(status_path):
                    with open(status_path, "r") as sf:
                        for line in sf:
                            if line.startswith("VmRSS:"):
                                res["rss_mib"] = round(int(line.split()[1]) / 1024.0, 1)
                                break
    except Exception:
        pass
    return res


def is_nvidia_gpu_suspended() -> bool:
    """Checks sysfs to determine if the discrete NVIDIA GPU is in PCIe runtime suspend (D3cold)."""
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
    Dynamically probes NVIDIA model and driver version from procfs without waking the PCIe device from D3cold.
    """
    info = {"name": "NVIDIA GPU", "driver": "N/A"}
    for p in glob.glob("/proc/driver/nvidia/gpus/*/information"):
        try:
            with open(p, "r") as f:
                for line in f:
                    if line.startswith("Model:"):
                        info["name"] = line.split(":", 1)[1].strip()
                        break
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
    return info


# --- Native NVML Engine via ctypes ---

class NvmlTelemetry:
    """Zero-overhead NVIDIA telemetry querying libnvidia-ml.so.1 in sub-milliseconds."""

    def __init__(self, allow_wake: bool = False):
        self.available = False
        self.suspended = False
        self._dev = None
        self._nvml = None
        self.name = "NVIDIA GPU"
        self.driver_version = "N/A"
        self.memory_total_mib: Optional[int] = None
        self.power_limit_w: Optional[float] = None
        self._allow_wake = allow_wake

        if not allow_wake and is_nvidia_gpu_suspended():
            self.suspended = True
            cache = _load_gpu_cache()
            if cache and cache.get("name"):
                self.name = cache.get("name", self.name)
                self.driver_version = cache.get("driver", self.driver_version)
                self.memory_total_mib = cache.get("memory_total_mib")
                self.power_limit_w = cache.get("power_limit_w")
            else:
                proc_info = _probe_nvidia_procfs()
                self.name = proc_info.get("name", self.name)
                self.driver_version = proc_info.get("driver", self.driver_version)
            return

        self._init_nvml()

    def _init_nvml(self):
        """Initializes NVML bindings via ctypes."""
        try:
            self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
            if self._nvml.nvmlInit() != 0:
                return

            self._dev = ctypes.c_void_p()
            if self._nvml.nvmlDeviceGetHandleByIndex(0, ctypes.byref(self._dev)) != 0:
                return

            name_buf = ctypes.create_string_buffer(64)
            if self._nvml.nvmlDeviceGetName(self._dev, name_buf, 64) == 0:
                self.name = name_buf.value.decode("utf-8", errors="replace")

            drv_buf = ctypes.create_string_buffer(64)
            if self._nvml.nvmlSystemGetDriverVersion(drv_buf, 64) == 0:
                self.driver_version = drv_buf.value.decode("utf-8", errors="replace")

            class _NvmlMemory(ctypes.Structure):
                _fields_ = [
                    ("total", ctypes.c_ulonglong),
                    ("free", ctypes.c_ulonglong),
                    ("used", ctypes.c_ulonglong),
                ]
            mem = _NvmlMemory()
            if self._nvml.nvmlDeviceGetMemoryInfo(self._dev, ctypes.byref(mem)) == 0:
                self.memory_total_mib = int(mem.total // (1024 * 1024))

            plimit = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetEnforcedPowerLimit(self._dev, ctypes.byref(plimit)) == 0:
                self.power_limit_w = round(plimit.value / 1000.0, 1)

            # Persist dynamically discovered specs to user cache
            _save_gpu_cache({
                "name": self.name,
                "driver": self.driver_version,
                "memory_total_mib": self.memory_total_mib,
                "power_limit_w": self.power_limit_w,
            })

            self.available = True
            self.suspended = False
        except Exception:
            self.available = False

    def query(self) -> Dict[str, Any]:
        """Queries current GPU metrics."""
        if self.suspended:
            if not is_nvidia_gpu_suspended():
                self._init_nvml()
            else:
                return {
                    "name": self.name,
                    "driver": self.driver_version,
                    "temperature_c": None,
                    "power_draw_w": 0.0,
                    "power_limit_w": self.power_limit_w,
                    "memory_used_mib": 0,
                    "memory_total_mib": self.memory_total_mib,
                    "memory_percent": 0.0,
                    "utilization_gpu": 0,
                    "utilization_mem": 0,
                    "clock_graphics_mhz": 0,
                    "clock_memory_mhz": 0,
                    "state": "suspended",
                }

        if not self.available or not self._dev:
            return self._fallback_query()

        res = {
            "name": self.name,
            "driver": self.driver_version,
            "temperature_c": None,
            "power_draw_w": None,
            "power_limit_w": None,
            "memory_used_mib": None,
            "memory_total_mib": None,
            "memory_percent": 0.0,
            "utilization_gpu": None,
            "utilization_mem": None,
            "clock_graphics_mhz": None,
            "clock_memory_mhz": None,
        }

        try:
            temp = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetTemperature(self._dev, 0, ctypes.byref(temp)) == 0:
                res["temperature_c"] = temp.value

            power = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetPowerUsage(self._dev, ctypes.byref(power)) == 0:
                res["power_draw_w"] = round(power.value / 1000.0, 1)

            plimit = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetEnforcedPowerLimit(self._dev, ctypes.byref(plimit)) == 0:
                res["power_limit_w"] = round(plimit.value / 1000.0, 1)

            class _NvmlMemory(ctypes.Structure):
                _fields_ = [
                    ("total", ctypes.c_ulonglong),
                    ("free", ctypes.c_ulonglong),
                    ("used", ctypes.c_ulonglong),
                ]
            mem = _NvmlMemory()
            if self._nvml.nvmlDeviceGetMemoryInfo(self._dev, ctypes.byref(mem)) == 0:
                res["memory_used_mib"] = int(mem.used // (1024 * 1024))
                res["memory_total_mib"] = int(mem.total // (1024 * 1024))
                if res["memory_total_mib"] > 0:
                    res["memory_percent"] = round((res["memory_used_mib"] / res["memory_total_mib"]) * 100.0, 1)

            class _NvmlUtilization(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]
            util = _NvmlUtilization()
            if self._nvml.nvmlDeviceGetUtilizationRates(self._dev, ctypes.byref(util)) == 0:
                res["utilization_gpu"] = util.gpu
                res["utilization_mem"] = util.memory

            clk_gfx = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetClockInfo(self._dev, 0, ctypes.byref(clk_gfx)) == 0:
                res["clock_graphics_mhz"] = clk_gfx.value
            clk_mem = ctypes.c_uint()
            if self._nvml.nvmlDeviceGetClockInfo(self._dev, 2, ctypes.byref(clk_mem)) == 0:
                res["clock_memory_mhz"] = clk_mem.value
        except Exception:
            pass

        return res

    def _fallback_query(self) -> Dict[str, Any]:
        """Fallback to nvidia-smi if NVML C-library fails."""
        res = {
            "name": "NVIDIA GPU", "driver": "N/A", "temperature_c": None,
            "power_draw_w": None, "power_limit_w": None, "memory_used_mib": None,
            "memory_total_mib": None, "memory_percent": 0.0, "utilization_gpu": None,
            "utilization_mem": None, "clock_graphics_mhz": None, "clock_memory_mhz": None,
        }
        if not shutil.which("nvidia-smi"):
            return res

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,driver_version,temperature.gpu,power.draw,power.limit,utilization.gpu,memory.used,memory.total,clocks.current.graphics,clocks.current.memory",
                "--format=csv,noheader,nounits",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
            if proc.returncode == 0 and proc.stdout.strip():
                parts = [p.strip() for p in proc.stdout.strip().split(",")]
                if len(parts) >= 8:
                    res["name"] = parts[0]
                    res["driver"] = parts[1]
                    res["temperature_c"] = float(parts[2]) if parts[2] != "[N/A]" else None
                    res["power_draw_w"] = float(parts[3]) if parts[3] != "[N/A]" else None
                    res["power_limit_w"] = float(parts[4]) if parts[4] != "[N/A]" else None
                    res["utilization_gpu"] = int(parts[5]) if parts[5] != "[N/A]" else None
                    res["memory_used_mib"] = int(float(parts[6])) if parts[6] != "[N/A]" else None
                    res["memory_total_mib"] = int(float(parts[7])) if parts[7] != "[N/A]" else None
                    if res["memory_used_mib"] and res["memory_total_mib"]:
                        res["memory_percent"] = round((res["memory_used_mib"] / res["memory_total_mib"]) * 100.0, 1)
                if len(parts) >= 10:
                    res["clock_graphics_mhz"] = int(float(parts[8])) if parts[8] != "[N/A]" else None
                    res["clock_memory_mhz"] = int(float(parts[9])) if parts[9] != "[N/A]" else None
        except Exception:
            pass

        return res

    def close(self):
        """Releases NVML resources."""
        if self._nvml and self.available:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
