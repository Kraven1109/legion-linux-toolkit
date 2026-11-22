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
| **`lstats`** | Hardware & Platform Telemetry CLI | `lstats` (2×2 TUI dashboard), `-w` (Interactive live TUI), `-j` (JSON), `-s` (Short) |
| **`lbat`** | Battery Conservation Mode | `status`, `on` (~80% cap), `off` (100% full), `toggle` |
| **`lmode`** | Power & Thermal Manager | `status`, `next` (Fn+Q loop), `quiet`, `balanced`, `perf`, `extreme` |
| **`lhz`** | Display Refresh Rate | `status`, `toggle` (240Hz $\leftrightarrow$ 60Hz), `240`, `60`, `fix` |
| **`lcolor`** | Display Color Profile Manager | `status`, `cycle` (Fn+L), `set <name>`, `list` |
| **`lcopilot`** | External Keyboard & CLI Copilot Trigger | `tap` (Smart Terminal), `hold` / `menu` (Quick Launch), `fn-n` |
| **`test-hotkey`** | Hardware Event Sniffer | Real-time evdev scancode & keycode diagnostic tool |

---

### 📊 `lstats` — Hardware & Platform Telemetry Dashboard

`lstats` is a zero-bloat, native Python CLI dashboard using pure standard library modules (`ctypes`, `os`, `sys`, `struct`, `json`). It renders a responsive **2×2 card grid** (`THERMAL & COOLING`, `POWER & BATTERY`, `COMPUTE & MEMORY`, `DISPLAYS & CALIBRATION`) that adapts cleanly from 76 to 136+ columns with segmented progress gauges, live trend arrows (`↑` / `↓`), and interactive single-key controls in watch mode (`[p]` Profile, `[1-4]` Direct Mode, `[c]` 80% Cap, `[r]` 240/60Hz, `[l]` Color Profile, `[s]` Drop to Shell, `[q]` Quit):

* **CPU (Intel & AMD):** Package temperature (`coretemp` / `k10temp`), average & peak boost frequency, system utilization %, **live RAPL package power draw (W)**, and synchronized **MMIO RAPL PL1/PL2 limits**.
* **dGPU (NVIDIA RTX 30/40/50 Series):** Native NVML via `ctypes` querying temperature, live wattage vs. active TGP (`150W` / `175W`), VRAM used/total/free GiB, GPU utilization %, graphics clock, and automatic **PCIe D3cold Sleep (`0.0 W`)** detection without waking suspended GPUs.
* **iGPU (Intel i915/xe & AMD Radeon):** Direct kernel PMU engine busyness via `perf_event_open()` (`rcs0` Render/3D, `ccs0` Compute, `vcs0` Video, `bcs0` Copy) scaled by actual/max GT frequency (`MHz`), plus live **RAPL PP1 power draw (W)**.
* **Cooling Fans (Triple & Dual Fan Topologies):** Native `lenovo_wmi_other` readings for CPU Fan (max 5200 RPM), GPU Fan (max 5400 RPM), and Hyperchamber Aux Fan (max 6500 RPM, automatically hidden on dual-fan laptops).
* **Memory & Per-Drive NVMe Storage:** DDR5 SPD thermal sensors (`spd5118`) paired with live **SMBIOS Type 17** bus speed and DIMM topology (e.g., `DDR5-6400 (2x32GB Micron)`), plus individual NVMe SSD telemetry (`SSD1`, `SSD2`) reporting model, capacity, and active PCIe link generation/width (`Gen4 x4`, `Gen5 x4`).
* **Power & Battery:** Battery charge %, AC/Battery source, health %, cycle count, voltage, and Conservation Mode (~80% cap vs. 100%).
* **Displays, Color Calibration & GPU MUX Routing:** Multi-monitor EDID parser, column-aligned resolution/scale/refresh rate, active factory ICC color profile (`sRGB`, `Display P3`, `DCI-P3`, `Adobe RGB`, `Rec.709`, `Native`), and per-connector hardware **GPU MUX routing** (`DP-3 ➔ dGPU`, `eDP-1 ➔ iGPU`).

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
│   ├── lenovo_platform_profile.conf
│   └── lenovo_rapl_mmio.conf
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
