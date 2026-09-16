# Lenovo Legion Pro 7 (16IAX10H) Hardware & Linux Native Features Guide

Comprehensive hardware reference and native Linux control guide for the **Lenovo Legion Pro 7 16IAX10H** running **CachyOS** (Kernel 7.2+).

---

## 1. Verified Exact System Specifications

| Component | Specification |
| :--- | :--- |
| **Model** | **Lenovo Legion Pro 7 16IAX10H** (Type `83F5`, BIOS `Q7CN78WW`) |
| **CPU** | **Intel® Core™ Ultra 9 275HX** (Arrow Lake-HX, 24 Cores / 24 Threads) |
| **dGPU** | **NVIDIA® GeForce RTX™ 5090 Laptop GPU** (24 GB GDDR7 VRAM, Blackwell `GB203M`) |
| **iGPU** | Intel® Arrow Lake-S Graphics |
| **RAM** | **64 GB DDR5** (2x32GB SPD5118 high-speed modules) |
| **Display** | 16" 2.5K WQXGA (**2560x1600**) @ **240 Hz** (DCI-P3 Color Calibrated) |
| **Battery** | **99.9 Wh** Li-Polymer (100% capacity, ~17 charge cycles) |

---

## 2. Power & Thermal Management (`lmode` & `Fn + Q` Unified OSD)

Lenovo Legion Pro 7 supports 5 power envelopes at the hardware/ACPI level via `/sys/firmware/acpi/platform_profile`.

Both the **physical hardware key <kbd>Fn</kbd> + <kbd>Q</kbd>** and the custom CLI tool **`lmode`** are unified: triggering either one switches the power envelope, updates the power button LED color, and pops up an on-screen OSD notification banner.

---

### A. Native Hardware / ACPI Interface & Available Profiles

* **Platform Profile Node:** `/sys/firmware/acpi/platform_profile`
* **Supported Choices Node:** `/sys/firmware/acpi/platform_profile_choices`
* **Native Raw Commands:**
  ```bash
  echo max-power   | sudo tee /sys/firmware/acpi/platform_profile  # Extreme Mode (Purple)
  echo performance | sudo tee /sys/firmware/acpi/platform_profile  # Performance Mode (Red)
  echo balanced    | sudo tee /sys/firmware/acpi/platform_profile  # Balanced Mode (White)
  echo low-power   | sudo tee /sys/firmware/acpi/platform_profile  # Quiet Mode (Blue)
  ```

#### Hardware Profiles & Power Button LED:
* **`low-power` (Quiet Mode - 🔵 Blue LED):** Limits fan noise and power draw; ideal for battery, media, and silent work. *(Part of Fn+Q loop).*
* **`balanced` (Auto/Balanced - ⚪ White LED):** Dynamic auto power allocation based on system load. *(Part of Fn+Q loop).*
* **`performance` (Performance - 🔴 Red LED):** Unlocks full 175W TGP for RTX 5090 and high PL1/PL2 for Core Ultra 9 275HX. *(Part of Fn+Q loop).*
* **`max-power` (Extreme Mode - 🟣 Purple LED):** Maximum cooling fan curves and peak overclocking headroom for intense LLM workloads. *(Extended profile; switch directly via `lmode extreme` or `lmode 4`).*
* **`custom` (Custom Mode - ⚙️ Disabled on Linux):** Requires pre-loaded EC fan curve and power limit tables (configured via Lenovo Vantage on Windows). Disabled in `lmode` to prevent EC errors.

> **Hardware <kbd>Fn</kbd> + <kbd>Q</kbd> Loop Specification:**
> On the Legion Pro 7 (16IAX10H), the physical <kbd>Fn</kbd> + <kbd>Q</kbd> hardware key in firmware cycles strictly through **3 standard modes**:
> $$\\text{Quiet (Blue)} \\longrightarrow \\text{Balanced (White)} \\longrightarrow \\text{Performance (Red)} \\longrightarrow \\text{Quiet (Blue)}$$
> To maintain 100% behavioral equivalence, `lmode next` follows this exact 3-step loop.

---

### B. How the Custom Sudo-less CLI & Kernel OSD Were Built

Because KDE Plasma does not natively provide an OSD for external ACPI hardware profile changes, and sysfs nodes reset to root-only `0644` upon reboot, we built a non-intrusive, event-driven stack:

#### Step 1: Grant non-root write access on boot via `tmpfiles.d`
Create `/etc/tmpfiles.d/lenovo_platform_profile.conf`:
```text
z /sys/firmware/acpi/platform_profile 0666 root root -
```
Apply immediately:
```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_platform_profile.conf
```

> **Vì sao cần tmpfiles.d?**
> Giống như node pin `conservation_mode`, node ACPI `/sys/firmware/acpi/platform_profile` nằm trên sysfs ảo trong RAM. Thiết lập này đảm bảo sau mỗi lần khởi động máy, quyền ghi `0666` được áp dụng ngay lập tức, cho phép người dùng chuyển profile qua script hoặc phím tắt mà không cần gõ `sudo`.

#### Step 2: Create the Adaptive CLI Tool `~/.local/bin/lmode`
Features:
- Dynamically queries available profiles from hardware choices node.
- Live telemetry reading real-time fan RPMs (CPU, GPU, and Exhaust) via `sensors`.
- Exact hardware matching: `lmode next` cycles through the 3 standard modes (Quiet ➔ Balanced ➔ Performance).
- Clean notice and English hint if `custom` is invoked.

```bash
cat << 'EOF' > ~/.local/bin/lmode
#!/usr/bin/env bash
set -euo pipefail

NODE="/sys/firmware/acpi/platform_profile"
CHOICES_NODE="/sys/firmware/acpi/platform_profile_choices"

if [[ ! -f "$NODE" ]]; then
    echo "[ERROR] ACPI platform_profile node not found at: $NODE" >&2
    exit 1
fi

get_choices() {
    if [[ -f "$CHOICES_NODE" ]]; then
        cat "$CHOICES_NODE"
    else
        echo "low-power balanced performance"
    fi
}

get_fans() {
    if command -v sensors >/dev/null 2>&1; then
        sensors 2>/dev/null | grep -E "fan[124]:" | awk '{print $1, $2, $3}' | tr '\n' ' | ' | sed 's/ | $//' || true
    fi
}

get_mode_desc() {
    local mode="$1"
    case "$mode" in
        low-power)
            echo -e "\033[1;34mQuiet\033[0m (Blue LED) • Silent fans, power saving"
            ;;
        balanced)
            echo -e "\033[1;37mBalanced\033[0m (White LED) • Auto dynamic allocation"
            ;;
        performance)
            echo -e "\033[1;31mPerformance\033[0m (Red LED) • Full 175W TGP & high boost"
            ;;
        max-power)
            echo -e "\033[1;35mExtreme\033[0m (Purple LED) • Max fan curves & peak power"
            ;;
        custom)
            echo -e "\033[0;90mCustom\033[0m \033[0;33m[Disabled]\033[0m • Requires Lenovo Vantage EC tables"
            ;;
        *)
            echo "$mode"
            ;;
    esac
}

get_status() {
    local current
    current=$(cat "$NODE")
    local fans
    fans=$(get_fans)
    local choices_str
    choices_str=$(get_choices)
    read -ra choices <<< "$choices_str"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e " 🚀 \033[1mPower & Thermal Manager\033[0m"
    echo "────────────────────────────────────────────────────────────────────"
    
    # Active mode line
    case "$current" in
        low-power)
            echo -e "  Active Mode:  \033[1;34m[●] Quiet Mode (Blue LED)\033[0m"
            echo "                Silent fans, low power draw, battery-saving"
            ;;
        balanced)
            echo -e "  Active Mode:  \033[1;37m[●] Balanced Mode (White LED)\033[0m"
            echo "                Dynamic auto power allocation"
            ;;
        performance)
            echo -e "  Active Mode:  \033[1;31m[●] Performance Mode (Red LED)\033[0m"
            echo "                Full 175W TGP for RTX 5090 & high CPU boost"
            ;;
        max-power)
            echo -e "  Active Mode:  \033[1;35m[●] Extreme Mode (Purple LED)\033[0m"
            echo "                Max cooling fan curves & peak overclocking"
            ;;
        custom)
            echo -e "  Active Mode:  \033[1;36m[●] Custom Mode\033[0m"
            echo "                Custom EC thermal envelope & fan curves"
            ;;
        *)
            echo -e "  Active Mode:  [●] $current"
            ;;
    esac

    if [[ -n "$fans" ]]; then
        echo -e "  Fans:         🌀 $fans"
    fi

    echo "────────────────────────────────────────────────────────────────────"
    echo -e "  \033[1mAvailable Profiles on this Device:\033[0m"
    for c in "${choices[@]}"; do
        local desc
        desc=$(get_mode_desc "$c")
        if [[ "$c" == "$current" ]]; then
            printf "    \033[1;32m●\033[0m %-14s %b \033[1;32m[ACTIVE]\033[0m\n" "$c" "$desc"
        elif [[ "$c" == "custom" ]]; then
            printf "    \033[0;90m-\033[0m \033[0;90m%-14s\033[0m %b\n" "$c" "$desc"
        else
            printf "    \033[0;37m○\033[0m %-14s %b\n" "$c" "$desc"
        fi
    done
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Switch: lmode <mode_name>  |  Cycle: lmode next (or Fn + Q)"
}

set_mode() {
    local target="$1"

    if [[ "$target" == "custom" ]]; then
        echo -e "\033[1;33m[NOTICE]\033[0m 'custom' profile is disabled on Linux."
        echo -e "\033[0;90mHint: Custom mode requires pre-loaded EC power & fan curve tables via Lenovo Vantage on Windows.\033[0m"
        echo -e "Please use: \033[1mquiet\033[0m (1), \033[1mbalanced\033[0m (2), \033[1mperf\033[0m (3), or \033[1mextreme\033[0m (4)."
        exit 1
    fi

    local choices_str
    choices_str=$(get_choices)
    read -ra choices <<< "$choices_str"

    # Validate target against available device choices
    local valid=0
    for c in "${choices[@]}"; do
        if [[ "$c" == "$target" ]]; then
            valid=1
            break
        fi
    done

    if [[ $valid -eq 0 ]]; then
        echo "[ERROR] Profile '$target' is not supported by your hardware." >&2
        echo "Supported profiles: $choices_str" >&2
        exit 1
    fi

    if [[ ! -w "$NODE" ]]; then
        echo "$target" | sudo tee "$NODE" >/dev/null
    else
        echo "$target" > "$NODE"
    fi
    echo -e "Switched to: \033[1m$target\033[0m"
}

cycle_next() {
    local current
    current=$(cat "$NODE")

    # Physical Fn+Q hardware loop on Legion Pro 7 cycles strictly through 3 standard modes:
    # Quiet (low-power) -> Balanced (balanced) -> Performance (performance) -> Quiet
    local cycle_list=("low-power" "balanced" "performance")

    local next="${cycle_list[0]}"
    for i in "${!cycle_list[@]}"; do
        if [[ "${cycle_list[$i]}" == "$current" ]]; then
            local next_idx=$(( (i + 1) % ${#cycle_list[@]} ))
            next="${cycle_list[$next_idx]}"
            break
        fi
    done

    set_mode "$next"
}

show_help() {
    local choices_str
    choices_str=$(get_choices)
    cat << HELP
Usage: lmode [command|profile]

Commands:
  status, (none)        Show active mode, live fan RPM, and all available device profiles
  next, toggle          Cycle to next mode (Fn+Q equivalent loop)
  help, -h              Show this help message

Direct Profile Shortcuts (Adaptive):
  quiet, low, 1         -> low-power (Blue LED)
  balanced, auto, 2     -> balanced (White LED)
  perf, performance, 3  -> performance (Red LED)
  extreme, max, 4       -> max-power (Purple LED)
  custom, 5             -> [Disabled] Requires EC power/fan tables

Hardware Supported Profiles:
  $choices_str
HELP
}

cmd="${1:-status}"

case "$cmd" in
    status)
        get_status
        ;;
    next|toggle)
        cycle_next
        ;;
    quiet|low|1)
        set_mode "low-power"
        ;;
    balanced|auto|2)
        set_mode "balanced"
        ;;
    perf|performance|3)
        set_mode "performance"
        ;;
    extreme|max|max-power|4)
        set_mode "max-power"
        ;;
    custom|5)
        set_mode "custom"
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        choices_str=$(get_choices)
        if [[ " $choices_str " =~ [[:space:]]$cmd[[:space:]] ]]; then
            set_mode "$cmd"
        else
            echo "[ERROR] Unknown command or unsupported profile: $cmd" >&2
            show_help
            exit 1
        fi
        ;;
esac
EOF
chmod +x ~/.local/bin/lmode
```

#### Step 3: Create the Unified Kernel & Hotkey OSD Daemon `~/.local/bin/legion-profile-osd`
Instead of using wasteful `while sleep` polling loops that drain battery and waste CPU cycles, this script uses Linux kernel `select.poll()`. It sleeps indefinitely in the kernel wait queue at **0% CPU** and handles both hardware triggers simultaneously:
1. Listens to `sysfs_notify()` on `/sys/firmware/acpi/platform_profile` for <kbd>Fn</kbd> + <kbd>Q</kbd> and `lmode`.
2. Listens to `KEY_REFRESH_RATE_TOGGLE` (Keycode `562`) on `/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event` for physical <kbd>Fn</kbd> + <kbd>R</kbd>.

To ensure stunning visual presentation matching each mode's Power Button LED color, we provide custom 64x64 SVG badges in `~/.local/share/icons/legion/` (`quiet.svg`, `balanced.svg`, `performance.svg`, `extreme.svg`, `custom.svg`), with automatic fallback to standard system icons.

> **Cloud Backup & Instant Restore:**
> All 5 SVG icons are permanently backed up to your OneDrive at:
> `~/OneDrive/CloudSync/Software/16iax10h-power-icons/`
> To restore or deploy them on any fresh Linux install:
> ```bash
> ~/OneDrive/CloudSync/Software/16iax10h-power-icons/install.sh
> ```

```bash
cat << 'EOF' > ~/.local/bin/legion-profile-osd
#!/usr/bin/env python3
import select
import subprocess
import sys
import os
import struct
import time

NODE = "/sys/firmware/acpi/platform_profile"
HOTKEY_NODE = "/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event"
LHZ_BIN = os.path.expanduser("~/.local/bin/lhz")
ICON_DIR = os.path.expanduser("~/.local/share/icons/legion")

# Linux Input Event Code for Display Refresh Rate Toggle (Fn+R)
KEY_REFRESH_RATE_TOGGLE = 562

PROFILES = {
    "low-power": {
        "title": "Quiet Mode",
        "msg": "🔵 Blue LED • Silent fans, power-saving",
        "icon_file": "quiet.svg",
        "fallback": "battery-charging"
    },
    "balanced": {
        "title": "Balanced Mode",
        "msg": "⚪ White LED • Dynamic auto power allocation",
        "icon_file": "balanced.svg",
        "fallback": "battery-profile-balanced"
    },
    "performance": {
        "title": "Performance Mode",
        "msg": "🔴 Red LED • Full 175W TGP & High CPU boost",
        "icon_file": "performance.svg",
        "fallback": "preferences-system-performance"
    },
    "max-power": {
        "title": "Extreme Mode",
        "msg": "🟣 Purple LED • Maximum fan curves & peak power",
        "icon_file": "extreme.svg",
        "fallback": "speedometer"
    },
    "custom": {
        "title": "Custom Mode",
        "msg": "Custom thermal envelope & curves",
        "icon_file": "custom.svg",
        "fallback": "preferences-system"
    }
}

def send_osd(state):
    info = PROFILES.get(state, {
        "title": f"Profile: {state}",
        "msg": "ACPI platform_profile changed",
        "icon_file": "custom.svg",
        "fallback": "preferences-system-power-management"
    })
    
    icon_path = os.path.join(ICON_DIR, info["icon_file"])
    icon = icon_path if os.path.isfile(icon_path) else info["fallback"]

    cmd = [
        "notify-send",
        "-a", "Legion Profile",
        "-i", icon,
        "-h", "string:x-canonical-private-synchronous:legion-profile-osd",
        "-t", "1800",
        info["title"],
        info["msg"]
    ]
    try:
        subprocess.run(cmd, check=False)
    except Exception:
        pass

def main():
    poller = select.poll()

    # 1. Register ACPI platform_profile for Fn+Q & lmode
    profile_file = None
    last_profile_state = ""
    if os.path.exists(NODE):
        try:
            profile_file = open(NODE, "r")
            last_profile_state = profile_file.read().strip()
            poller.register(profile_file, select.POLLPRI | select.POLLERR)
        except Exception:
            pass

    # 2. Register Ideapad extra buttons node for Fn+R (KEY_REFRESH_RATE_TOGGLE)
    hotkey_fd = None
    if os.path.exists(HOTKEY_NODE):
        try:
            hotkey_fd = os.open(HOTKEY_NODE, os.O_RDONLY | os.O_NONBLOCK)
            poller.register(hotkey_fd, select.POLLIN | select.POLLERR)
        except Exception:
            pass

    last_toggle_time = 0

    try:
        while True:
            # Sleep indefinitely in kernel wait queue (0% CPU overhead)
            events = poller.poll()
            for fd, event in events:
                # Handle Profile change (Fn+Q)
                if profile_file and fd == profile_file.fileno():
                    profile_file.seek(0)
                    curr = profile_file.read().strip()
                    if curr and curr != last_profile_state:
                        send_osd(curr)
                        last_profile_state = curr

                # Handle Refresh Rate toggle (Fn+R)
                elif hotkey_fd and fd == hotkey_fd:
                    while True:
                        try:
                            data = os.read(hotkey_fd, 24)
                            if len(data) < 24:
                                break
                            sec, usec, etype, code, value = struct.unpack("qqHHI", data)
                            # etype 1 = EV_KEY, value 1 = PRESS
                            if etype == 1 and code == KEY_REFRESH_RATE_TOGGLE and value == 1:
                                now = time.time()
                                if now - last_toggle_time > 0.4: # Debounce
                                    last_toggle_time = now
                                    if os.path.isfile(LHZ_BIN):
                                        subprocess.run([LHZ_BIN, "toggle"], check=False)
                        except BlockingIOError:
                            break
                        except Exception:
                            break
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
EOF
chmod +x ~/.local/bin/legion-profile-osd
```

#### Step 4: Create & Enable the Systemd User Service
To ensure the OSD daemon runs continuously in the background under the user session:

Create `~/.config/systemd/user/legion-profile-osd.service`:
```ini
[Unit]
Description=Legion Fn+Q & lmode Profile OSD (Kernel Event Hook)
After=graphical-session.target

[Service]
ExecStart=%h/.local/bin/legion-profile-osd
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
```

Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable --now legion-profile-osd.service
```

Check status:
```bash
systemctl --user status legion-profile-osd.service
```

#### Step 5: Everyday Usage (Unified CLI & Hardware Key)
```bash
lmode            # Adaptive status card: shows active mode, live fan RPMs, and ALL hardware profiles
lmode next       # Cycle to next mode (Exact Fn+Q 3-mode loop: Quiet ➔ Balanced ➔ Performance)
lmode quiet      # Directly switch to Quiet Mode (Blue LED)
lmode balanced   # Directly switch to Balanced Mode (White LED)
lmode perf       # Directly switch to Performance Mode (Red LED)
lmode extreme    # Directly switch to Extreme Mode (Purple LED)
lmode custom     # Displays English hint explaining why custom mode is disabled on Linux
```

*(Pressing the physical keyboard shortcut <kbd>Fn</kbd> + <kbd>Q</kbd> or running `lmode next` triggers the exact same LED color change and identical OSD notification banner).*

---

## 3. Real-time Fan Monitoring & Turbo Mode

The kernel driver `lenovo_wmi_other` natively exposes live RPM telemetry for all 3 fans:
* **Fan 1 (CPU):** e.g., ~4400 RPM
* **Fan 2 (GPU):** e.g., ~4500 RPM
* **Fan 4 (Vapor Chamber / Exhaust):** e.g., ~5500 RPM

View real-time fan speeds and temperatures:
```bash
sensors
```

### Force Maximum Fan Speed (Dust Cleaning / Turbo Cooling):
```bash
echo 1 | sudo tee /sys/bus/platform/devices/VPC2004:00/fan_mode   # 100% Full Blast Fans
echo 0 | sudo tee /sys/bus/platform/devices/VPC2004:00/fan_mode   # Return to Auto Fans
```

---

## 4. Battery Conservation Mode & Custom CLI (`lbat`)

### A. Native Hardware / ACPI Interface
The kernel exposes the battery threshold directly through the `ideapad_laptop` platform driver:
* **Sysfs Node:** `/sys/bus/platform/devices/VPC2004:00/conservation_mode`
* **Native Raw Commands:**
  ```bash
  echo 1 | sudo tee /sys/bus/platform/devices/VPC2004:00/conservation_mode  # Cap charge at ~80%
  echo 0 | sudo tee /sys/bus/platform/devices/VPC2004:00/conservation_mode  # Allow full 100% charge
  ```

---

### B. How the Custom CLI `lbat` Was Built (Sudo-less Setup)

To avoid typing `sudo` and remembering the long sysfs path, we created a custom wrapper tool at `~/.local/bin/lbat`:

#### Step 1: Grant non-root write access on boot via `tmpfiles.d`
Create `/etc/tmpfiles.d/lenovo_conservation.conf`:
```text
z /sys/bus/platform/devices/VPC2004:00/conservation_mode 0666 root root -
```
Apply immediately:
```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_conservation.conf
```

> **Giải thích cú pháp `tmpfiles.d`:**
> * `z` *(Action)*: Điều chỉnh quyền (permission) nếu node đã tồn tại, không tự ý tạo mới nếu file chưa có.
> * `Path`: Đường dẫn sysfs đến node pin của Lenovo.
> * `0666` *(Mode)*: Cấp quyền đọc/ghi (`rw-rw-rw-`), cho phép user thường ghi dữ liệu mà không cần sudo.
> * `root root` *(User / Group)*: Giữ quyền sở hữu thuộc về root.
> * `-` *(Age / Cleanup)*: Bỏ qua quy tắc dọn dẹp file theo thời gian.
>
> **Vì sao cần dùng cơ chế này?**
> Thư mục `/sys` là filesystem ảo trong RAM, được kernel tạo mới mỗi lần bật máy với quyền mặc định `0644` (chỉ root được ghi). Nhờ quy tắc `tmpfiles.d`, systemd sẽ tự động gán lại quyền `0666` ngay khi vừa boot xong, giúp các script hoặc phím tắt người dùng chạy tức thì mà không bao giờ bị hỏi mật khẩu sudo.


#### Step 2: Create the script at `~/.local/bin/lbat`
```bash
cat << 'EOF' > ~/.local/bin/lbat
#!/usr/bin/env bash
set -euo pipefail

NODE="/sys/devices/pci0000:00/0000:00:1f.0/PNP0C09:00/VPC2004:00/conservation_mode"
BAT_DIR="/sys/class/power_supply/BAT0"

if [[ ! -f "$NODE" ]]; then
    # Fallback search if PCI topology or ACPI tree ever shifts
    FOUND=$(find /sys/devices/ -name "conservation_mode" 2>/dev/null | head -n 1 || true)
    if [[ -n "$FOUND" && -f "$FOUND" ]]; then
        NODE="$FOUND"
    else
        echo "[ERROR] Lenovo conservation mode node not found." >&2
        exit 1
    fi
fi

notify() {
    local msg="$1"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -a "Battery Manager" "Lenovo Battery" "$msg" 2>/dev/null || true
    fi
}

get_status() {
    local mode
    mode=$(cat "$NODE")
    local cap="N/A"
    local state="N/A"

    if [[ -d "$BAT_DIR" ]]; then
        [[ -f "$BAT_DIR/capacity" ]] && cap="$(cat "$BAT_DIR/capacity")%"
        [[ -f "$BAT_DIR/status" ]] && state="$(cat "$BAT_DIR/status")"
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " 🔋 Battery: $cap ($state)"
    if [[ "$mode" == "1" ]]; then
        echo -e " 🛡️  Mode:    \033[1;32m[ON] Conservation Mode\033[0m"
        echo "           (Charge capped at ~75–80% to extend battery lifespan)"
    else
        echo -e " ⚡ Mode:    \033[1;33m[OFF] Full Charge Mode\033[0m"
        echo "           (Charging to 100% enabled for travel / mobile use)"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

set_mode() {
    local target="$1"
    if [[ ! -w "$NODE" ]]; then
        echo "$target" | sudo tee "$NODE" >/dev/null
    else
        echo "$target" > "$NODE"
    fi

    if [[ "$target" == "1" ]]; then
        echo -e "✅ \033[1;32mConservation Mode ENABLED\033[0m (Capped at ~80%)"
        notify "Conservation Mode ON: Charge capped at ~80%"
    else
        echo -e "⚡ \033[1;33mFull Charge Mode ENABLED\033[0m (Charging to 100%)"
        notify "Full Charge ON: Charging to 100% enabled"
    fi
}

toggle_mode() {
    local current
    current=$(cat "$NODE")
    if [[ "$current" == "1" ]]; then
        set_mode 0
    else
        set_mode 1
    fi
}

show_help() {
    cat << 'HELP'
Usage: lbat [command]

Commands:
  status, (none)   Show current battery level & conservation mode
  on, save, 80     Enable conservation mode (cap charging at ~80%)
  off, full, 100   Disable conservation mode (allow full 100% charge)
  toggle           Switch between 80% cap and 100% full charge
  help, -h         Show this help message
HELP
}

cmd="${1:-status}"

case "$cmd" in
    status)
        get_status
        ;;
    on|save|80)
        set_mode 1
        ;;
    off|full|100)
        set_mode 0
        ;;
    toggle)
        toggle_mode
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        echo "[ERROR] Unknown command: $cmd" >&2
        show_help
        exit 1
        ;;
esac
EOF
chmod +x ~/.local/bin/lbat
```

#### Step 3: Everyday Usage (No sudo required):
```bash
lbat           # View current battery level & conservation state
lbat on        # Enable ~80% charge cap (Desktop plugged use)
lbat off       # Enable 100% full charge (Mobile / travel use)
lbat toggle    # One-key quick toggle
```

---

## 5. Display Refresh Rate Switching (`lhz` & <kbd>Fn</kbd> + <kbd>R</kbd> OSD)

The 16" 2.5K WQXGA (2560x1600) display supports dynamic refresh rate switching between **240.00 Hz** (maximum responsiveness and fluid gaming) and **60.00 Hz** (maximum battery saving when on the go).

Both the **physical hardware key <kbd>Fn</kbd> + <kbd>R</kbd>** and the custom CLI tool **`lhz`** are unified: triggering either one switches the display timing, updates the rate without screen flickering, and pops up an on-screen OSD notification banner.

---

### A. Native Hardware & Kernel Interface
Under KDE Plasma 6 Wayland, display modes are managed directly by the compositor via `kscreen-doctor`, and hardware keypresses are handled by the `ideapad_laptop` platform driver:
* **Display Output:** `eDP-1` (Internal Panel)
* **Mode 1:** `2560x1600@240.00 Hz` (Default / Max Performance)
* **Mode 2:** `2560x1600@60.00 Hz` (Power Saving)
* **Hardware Event Node:** `/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event`
* **Hardware Scancode / Keycode:** Scancode `0x0110` ➔ Keycode `562` (`KEY_REFRESH_RATE_TOGGLE`)
* **Native Raw Commands:**
  ```bash
  kscreen-doctor output.1.mode.1   # Set 2560x1600 @ 240.00 Hz
  kscreen-doctor output.1.mode.2   # Set 2560x1600 @ 60.00 Hz
  ```

---

### B. How the Custom Sudo-less Tooling Was Built (`tmpfiles.d` & Daemon Hook)

To provide instant toggling, telemetry status cards, and seamless hardware <kbd>Fn</kbd> + <kbd>R</kbd> key handling without installing third-party bloatware, we built a dedicated stack:

#### Step 1: Grant non-root access to the hotkey event node via `tmpfiles.d`
Create `/etc/tmpfiles.d/lenovo_hotkeys.conf`:
```text
z /dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event 0666 root root -
```
Apply immediately:
```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_hotkeys.conf
```

> **Giải thích kiến trúc tmpfiles.d đồng bộ:**
> Tương tự như `lenovo_conservation.conf` và `lenovo_platform_profile.conf`, quy tắc này giúp node sự kiện phím tắt của Lenovo luôn nhận quyền đọc `0666` ngay từ lúc boot máy (`systemd-tmpfiles-setup-dev.service`), cho phép daemon người dùng `legion-profile-osd` lắng nghe phím <kbd>Fn</kbd> + <kbd>R</kbd> trực tiếp mà không cần quyền root.

#### Step 2: Create the CLI Tool `~/.local/bin/lhz`
Features:
- Dynamically detects the active refresh rate via `kscreen-doctor -o`.
- Toggles between 240Hz and 60Hz instantly without screen flickering or root privileges.
- Triggers a rich on-screen OSD notification banner.

```bash
cat << 'EOF' > ~/.local/bin/lhz
#!/usr/bin/env bash
set -euo pipefail

# Query current active rate on primary display
get_current_rate() {
    kscreen-doctor -o | grep -oE "@[0-9.]+\*" | tr -d '@*' | head -n 1 || true
}

send_osd() {
    local rate="$1"
    if [[ "$rate" == "240" ]]; then
        notify-send -a "Display Refresh Rate" \
            -i "video-display" \
            -h "string:x-canonical-private-synchronous:display-hz" \
            -t 1800 \
            "Refresh Rate: 240 Hz" \
            "⚡ Ultra Smooth • Maximum Gaming Performance"
    else
        notify-send -a "Display Refresh Rate" \
            -i "video-display" \
            -h "string:x-canonical-private-synchronous:display-hz" \
            -t 1800 \
            "Refresh Rate: 60 Hz" \
            "🔋 Battery Saver • Low Power Consumption"
    fi
}

set_rate() {
    local target="$1"
    if [[ "$target" == "240" ]]; then
        kscreen-doctor output.1.mode.1 >/dev/null 2>&1
        send_osd "240"
        echo -e "Switched to: \033[1;32m240 Hz\033[0m"
    elif [[ "$target" == "60" ]]; then
        kscreen-doctor output.1.mode.2 >/dev/null 2>&1
        send_osd "60"
        echo -e "Switched to: \033[1;33m60 Hz\033[0m"
    else
        echo "[ERROR] Invalid rate: $target. Use 240 or 60." >&2
        exit 1
    fi
}

toggle_rate() {
    local current
    current=$(get_current_rate)
    if [[ "$current" =~ 240 ]]; then
        set_rate "60"
    else
        set_rate "240"
    fi
}

show_status() {
    local current
    current=$(get_current_rate)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e " 🖥️  \033[1mDisplay Refresh Rate Controller\033[0m"
    echo "────────────────────────────────────────────────────────────────────"
    if [[ "$current" =~ 240 ]]; then
        echo -e "  Active Rate:  \033[1;32m● 240.00 Hz (Max Smoothness)\033[0m"
        echo "                Panel: 2560x1600 WQXGA @ 240 Hz"
    elif [[ "$current" =~ 60 ]]; then
        echo -e "  Active Rate:  \033[1;33m● 60.00 Hz (Battery Saver)\033[0m"
        echo "                Panel: 2560x1600 WQXGA @ 60 Hz"
    else
        echo -e "  Active Rate:  $current Hz"
    fi
    echo "────────────────────────────────────────────────────────────────────"
    echo "  Toggle: lhz toggle  |  Direct: lhz 240  or  lhz 60"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

cmd="${1:-status}"

case "$cmd" in
    status)
        show_status
        ;;
    toggle)
        toggle_rate
        ;;
    240|high|max)
        set_rate "240"
        ;;
    60|low|save)
        set_rate "60"
        ;;
    help|-h|--help)
        echo "Usage: lhz [status|toggle|240|60]"
        ;;
    *)
        echo "[ERROR] Unknown command: $cmd" >&2
        exit 1
        ;;
esac
EOF
chmod +x ~/.local/bin/lhz
```

#### Step 3: Create the KDE Desktop Entry (Optional Alternative Shortcut)
To allow binding to any alternative global keyboard shortcut (e.g., <kbd>Meta</kbd> + <kbd>R</kbd>) directly in KDE Plasma:

Create `~/.local/share/applications/lhz-toggle.desktop`:
```ini
[Desktop Entry]
Name=Toggle Display Refresh Rate
Comment=Toggle between 240Hz and 60Hz refresh rate on Legion Pro 7
Exec=/home/quangtm/.local/bin/lhz toggle
Icon=video-display
Type=Application
Categories=System;Utility;
StartupNotify=false
```

Update desktop database:
```bash
kbuildsycoca6 2>/dev/null || true
```

#### Step 4: Everyday Usage (Unified CLI & Physical Key)
```bash
lhz              # Status card: shows current active refresh rate and panel resolution
lhz toggle       # One-command toggle between 240Hz and 60Hz + OSD notification banner
lhz 240          # Directly force 240.00 Hz (Gaming / Plugged in)
lhz 60           # Directly force 60.00 Hz (Battery saving / Travel)
```

*(Pressing the physical keyboard shortcut <kbd>Fn</kbd> + <kbd>R</kbd> or running `lhz toggle` triggers the exact same display mode switch and identical OSD notification banner).*

---

## 6. Hardware Privacy & Convenience Controls

### A. Electronic Camera Shutter (`camera_power`)
Electronically disconnects the Luxvisions webcam at the USB bus level:
```bash
echo 0 | sudo tee /sys/bus/platform/devices/VPC2004:00/camera_power   # Cut camera power (OFF)
echo 1 | sudo tee /sys/bus/platform/devices/VPC2004:00/camera_power   # Enable camera power (ON)
```

### B. Always-On USB Charging (`usb_charging`)
Allows the rear USB port (with the battery icon) to charge phones/peripherals while the laptop is sleeping or turned off:
```bash
echo 1 | sudo tee /sys/bus/platform/devices/VPC2004:00/usb_charging   # Enable Always-On USB
echo 0 | sudo tee /sys/bus/platform/devices/VPC2004:00/usb_charging   # Disable
```

### C. Fn-Lock Toggle (`fn_lock`)
Switches top row keys between standard F1-F12 and Special/Media keys without rebooting into BIOS:
```bash
echo 1 | sudo tee /sys/bus/platform/devices/VPC2004:00/fn_lock   # F1-F12 primary
echo 0 | sudo tee /sys/bus/platform/devices/VPC2004:00/fn_lock   # Media keys primary
```

### D. Chassis & Logo Lighting (`Fn + L` & USB Controller Status)
On the Lenovo Legion Pro 7 (16IAX10H), the exterior "LEGION" logo light on the lid and rear port illuminations are controlled via an internal ITE USB HID microcontroller:
* **Hardware ID:** `048d:c193` (*Integrated Technology Express, Inc. Lenovo Lighting*)
* **Current Linux Status:** Unlike earlier generations where the logo was hardwired to an EC analog switch, Gen 10 routes all decorative lighting via USB HID. On Windows, Lenovo Vantage sends proprietary HID feature reports. On Linux, the kernel does not currently have an in-tree driver for `048d:c193`, so <kbd>Fn</kbd> + <kbd>L</kbd> remains dormant at the BIOS default state. To keep the system 100% clean and stable, no unverified third-party software is installed.

---

## 7. Diagnostics & Event Discovery Utilities (`test-hotkey`)

When discovering, reverse-engineering, or integrating new laptop hardware hotkeys, proprietary Fn combinations, or special input events on Linux, we built a standalone diagnostic tool: `test-hotkey`.

Located at `~/.local/bin/test-hotkey`.

### A. How It Works
* **Zero External Dependencies:** Written in pure Python using only standard library modules (`os`, `sys`, `glob`, `struct`, `select`, `fcntl`).
* **Auto-Discovery:** Automatically iterates over all `/dev/input/event*` nodes, queries human-readable device names via `ioctl(EVIOCGNAME)`, and listens non-blockingly across all devices simultaneously using `select()`.
* **Precision Decoding:** Unpacks standard 64-bit Linux `input_event` packets (`qqHHI`):
  * **`EV_KEY` (Type 1):** Reports exact Linux Keycode (e.g. `562` for `KEY_REFRESH_RATE_TOGGLE`) and state (`PRESS`, `RELEASE`, `REPEAT`).
  * **`EV_MSC` (Type 4):** Captures raw hardware scancodes (e.g. `0x0110`) emitted by the Embedded Controller (EC) before kernel keymapping.

---

### B. Complete Script (`~/.local/bin/test-hotkey`)

```bash
cat << 'EOF' > ~/.local/bin/test-hotkey
#!/usr/bin/env python3
import os, sys, glob, struct, select, time, fcntl

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🔍 LENOVO HOTKEY EVENT DETECTOR")
print("👉 Please press [Fn + R] now on your keyboard (press it 2-3 times)...")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

fds = []
names = {}
for path in sorted(glob.glob("/dev/input/event*")):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        buf = bytearray(256)
        try:
            fcntl.ioctl(fd, 0x82004506, buf)
            name = buf.split(b'\x00')[0].decode("utf-8", "ignore")
        except Exception:
            name = "Unknown"
        fds.append(fd)
        names[fd] = f"{os.path.basename(path)}: {name}"
    except Exception:
        pass

if not fds:
    print("\n❌ Permission denied: Cannot read /dev/input/event*.")
    print("👉 Please run in your terminal: sudo test-hotkey\n")
    sys.exit(1)

start = time.time()
found = False
while time.time() - start < 8:
    r, _, _ = select.select(fds, [], [], 0.5)
    for fd in r:
        while True:
            try:
                data = os.read(fd, 24)
                if len(data) < 24:
                    break
                sec, usec, etype, code, value = struct.unpack("qqHHI", data)
                if etype == 1: # EV_KEY
                    state = "PRESS" if value == 1 else ("RELEASE" if value == 0 else "REPEAT")
                    print(f"  [KEY EVENT] {names[fd]} -> Code: {code} (0x{code:04x}) | Action: {state}")
                    found = True
                elif etype == 4: # EV_MSC
                    print(f"  [RAW SCAN]  {names[fd]} -> Scancode: 0x{value:04x}")
                    found = True
            except BlockingIOError:
                break

if not found:
    print("\n⏱️ 8s elapsed: No hardware input event received from Fn+R.")
else:
    print("\n✅ Events successfully captured!")
EOF
chmod +x ~/.local/bin/test-hotkey
```

---

### C. Everyday Diagnostic Usage

To test and discover any unrecognized keys or buttons:
```bash
sudo ~/.local/bin/test-hotkey
```

**Example Discovery Output (Uncovering Lenovo Legion <kbd>Fn</kbd> + <kbd>R</kbd>):**
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 LENOVO HOTKEY EVENT DETECTOR
👉 Please press [Fn + R] now on your keyboard (press it 2-3 times)...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [RAW SCAN]  event9: Ideapad extra buttons -> Scancode: 0x0110
  [KEY EVENT] event9: Ideapad extra buttons -> Code: 562 (0x0232) | Action: PRESS
  [KEY EVENT] event9: Ideapad extra buttons -> Code: 562 (0x0232) | Action: RELEASE

✅ Events successfully captured!
```

