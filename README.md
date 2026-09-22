# Lenovo Legion Linux Toolkit

Native, zero-overhead hardware control suite and event-driven OSD daemon for the **Lenovo Legion Pro 7 (16IAX10H)** running **CachyOS / Arch Linux (Kernel 7.2+, KDE Plasma 6 Wayland)**.

---

## 🌟 Highlights

* **100% Native & Minimalist:** Zero third-party bloat (no OpenRGB, no proprietary daemons). Uses in-kernel platform drivers, sysfs, and native Wayland compositor interfaces.
* **Unified Sudo-less Access:** All hardware nodes (`conservation_mode`, `platform_profile`, and hotkey event nodes) are permission-managed via `/etc/tmpfiles.d/` (`0666`), enabling seamless daily workflows without typing `sudo`.
* **Zero-Overhead Event Daemon (0% CPU):** Background watcher (`legion-profile-osd`) blocks in the Linux kernel wait-queue using `select.poll()`. It sleeps indefinitely and only wakes up when triggered by hardware events (`sysfs_notify()` or `KEY_REFRESH_RATE_TOGGLE`).
* **Physical Hotkey Parity:**
  * **<kbd>Fn</kbd> + <kbd>Q</kbd>:** Standard 3-mode loop (Quiet ➔ Balanced ➔ Performance) + Power button LED synchronization + OSD pop-up.
  * **<kbd>Fn</kbd> + <kbd>R</kbd>:** Dynamic display refresh rate toggle (240Hz $\leftrightarrow$ 60Hz) + OSD pop-up.
* **Custom Visual Assets:** High-resolution circular SVG badges matching exact hardware LED states (`icons/*.svg`).
* **Multi-Agent Ready:** Includes universal architectural directives in `AGENTS.md` and `.agents/AGENTS.md` for Antigravity, GitHub Copilot, KiloCode, Cursor, and Claude Code.

---

## 🛠️ Included Tools

| Command | Purpose | Options / Modes |
| :--- | :--- | :--- |
| **`lstats`** | Hardware & Platform Telemetry CLI | `lstats` (TUI dashboard), `-w` (Live watch), `-j` (JSON), `-s` (Short) |
| **`lbat`** | Battery Conservation Mode | `status`, `on` (~80% cap), `off` (100% full), `toggle` |
| **`lmode`** | Power & Thermal Manager | `status`, `next` (Fn+Q loop), `quiet`, `balanced`, `perf`, `extreme` |
| **`lhz`** | Display Refresh Rate | `status`, `toggle` (240Hz $\leftrightarrow$ 60Hz), `240`, `60` |
| **`lcolor`** | Display Color Profile Manager | `status`, `cycle` (Fn+L), `set <name>`, `list` |
| **`test-hotkey`** | Hardware Event Sniffer | Real-time evdev scancode & keycode diagnostic tool |

---

### 📊 `lstats` — Hardware & Platform Telemetry Dashboard

`lstats` is a zero-bloat, native Python CLI dashboard that runs with sub-15ms execution time using pure standard library (`ctypes`, `os`, `sys`, `json`). It aggregates telemetry across all Legion subsystems:

* **CPU (Core Ultra 9 275HX):** Package temperature, frequency, system load, and **live RAPL package power draw (W)**.
* **GPU (RTX 5090 Mobile 24GB):** Native NVML via `ctypes` querying temperature, live wattage vs. TGP (150W/175W), VRAM used/total, GPU utilization %, and graphics/memory clocks.
* **Triple Independent PWM Fans:** Native `lenovo_wmi_other` readings for CPU Fan (max 5200 RPM), GPU Fan (max 5400 RPM), and Aux/Rear Fan (max 6500 RPM) with micro percentage gauges.
* **Thermals & Storage:** DDR5 SPD thermal sensors (`spd5118`), NVMe composite temperatures, and CPU package thermals.
* **Power & Battery:** Battery charge %, status, health %, cycle count, voltage, and Conservation Mode (~80% cap vs. 100%).
* **Display & Calibration:** Primary eDP panel (`SDC420B`), refresh rate (240Hz/60Hz), scaling factor, and active factory ICC color profile (sRGB, Display P3, DCI-P3, Adobe RGB, Rec.709, Native).

```bash
lstats         # Instant snapshot TUI dashboard (<15ms)
lstats -w      # Real-time interactive watch mode (1s interval, 'q' to exit)
lstats -j      # Export structured JSON for Waybar / Polybar / scripts
lstats -s      # Compact one-line status string
```

---

## 🚀 Quick Start / Deployment

To deploy or update all tools, services, icons, and permissions on your system:

```bash
./install.sh
```

---

## 📁 Repository Layout

```text
legion-linux-toolkit/
├── AGENTS.md                # Universal AI developer entrypoint
├── bin/                     # Standalone CLI tools (deployed to ~/.local/bin/)
│   ├── lbat
│   ├── lcolor
│   ├── legion_core.py       # Consolidated hardware & platform core library
│   ├── legion-profile-osd
│   ├── lhz
│   ├── lmode
│   ├── lstats               # Hardware telemetry dashboard
│   └── test-hotkey
├── color-profiles/          # Factory-calibrated ICC profiles & Dolby Vision PQ config
├── config/                  # Launcher themes (Rofi)
│   └── rofi/
│       └── legion-launcher.rasi
├── icons/                   # Custom circular SVG badges (deployed to ~/.local/share/icons/legion/)
│   ├── balanced.svg
│   ├── color-profile.svg
│   ├── custom.svg
│   ├── extreme.svg
│   ├── performance.svg
│   └── quiet.svg
├── systemd/                 # User service unit
│   └── legion-profile-osd.service
├── tmpfiles.d/              # Boot-time permission configurations (/etc/tmpfiles.d/)
│   ├── lenovo_conservation.conf
│   └── lenovo_platform_profile.conf
├── udev/                    # Udev rules for sudo-less hardware evdev access (/etc/udev/rules.d/)
│   └── 99-lenovo-input.rules
└── install.sh               # 1-click installer and deployer
```

---

## ⚠️ Disclaimer & Limitation of Liability

> **PLEASE READ CAREFULLY BEFORE USING THIS SOFTWARE**

* **Independent Project:** This software is an independent, open-source project and is **NOT** affiliated with, authorized, maintained, sponsored, or endorsed by Lenovo Group Limited or any of its affiliates.
* **Target Hardware:** This toolkit is specifically engineered and tested for the **Lenovo Legion Pro 7i Gen 10 (16IAX10H, Type `83F5`)**. Using this toolkit on other models or architectures may result in unexpected behavior.
* **Hardware Interaction Warning:** This toolkit interacts directly with low-level kernel drivers, ACPI subsystem nodes (`platform_profile`), Embedded Controller (EC) interfaces, and display frequencies. While designed defensively with safety checks, improper use or modification may cause system instability or thermal throttling.
* **No Warranty / "AS IS":** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
* **Limitation of Liability:** IN NO EVENT SHALL THE AUTHORS, COPYRIGHT HOLDERS, OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, HARDWARE DAMAGE, SYSTEM CRASHES, DATA LOSS, LOSS OF USE, OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — see the [LICENSE](LICENSE) file for full details.

---

## 📜 Architectural Directives for AI Agents

For guidelines on coding style, hardware constraints, safety rules, and filesystem integrity, consult [.agents/AGENTS.md](.agents/AGENTS.md).
