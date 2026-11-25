# AGENTS.md — Architectural Directives & Design Philosophy

> **Target Environment:** Lenovo Legion Pro 7 16IAX10H (Type `83F5`, BIOS `Q7CN78WW`)  
> **Operating System:** CachyOS Linux (Kernel 7.2+, KDE Plasma 6 Wayland, dual-boot with Windows 11)  
> **Audience:** AI Coding Assistants (Antigravity, Claude, ChatGPT, etc.) and System Maintainers  
> **Last Updated:** September 2026

---

## 1. System Context & Overview

This system is a high-performance gaming and AI workstation featuring an **Intel Core Ultra 9 275HX**, **NVIDIA RTX 5090 Laptop GPU (24GB GDDR7)**, and a **2.5K 240Hz display**.

All configurations, custom tooling, and hardware hooks on this machine follow a strict design philosophy: **maximum performance, zero bloat, pure native integration, and complete reproducibility**.

---

## 2. Core Architectural Commandments (The 7 Golden Rules)

Every AI agent working on this repository or operating system **MUST strictly adhere** to the following design rules:

### Rule 1: Strict Minimalism & 100% Native Architecture
* **NO Third-Party Helper Apps or Bloat:** Never suggest or install third-party GUI or CLI bloat (e.g., OpenRGB, Vantage clones, third-party background pollers) unless explicitly demanded by the user.
* **Kernel & Native First:** Always exploit existing in-kernel platform drivers (`ideapad_laptop`, `lenovo_wmi`, in-kernel `ntfs`), native sysfs interfaces, and native desktop compositors (`kscreen-doctor`, `notify-send`, `qdbus6`).

### Rule 2: Strict Permission Architecture (`/etc/tmpfiles.d/` for `/sys/`, `/etc/udev/rules.d/` for `/dev/input/`)
To ensure 100% sudo-less operation that persists across reboots without breaking, permissions MUST strictly adhere to this architectural boundary:
1. **`/sys/` Static Sysfs Nodes $\rightarrow$ Managed by `/etc/tmpfiles.d/*.conf`:**
   - `/etc/tmpfiles.d/lenovo_conservation.conf` $\rightarrow$ Battery charge cap (`0666` on `conservation_mode` for `lbat`).
   - `/etc/tmpfiles.d/lenovo_platform_profile.conf` $\rightarrow$ Power & thermal profiles (`0666` on `platform_profile` for `lmode` & Fn+Q).
   - `/etc/tmpfiles.d/lenovo_rapl_mmio.conf` $\rightarrow$ MMIO RAPL CPU package limits (`0666` on canonical non-symlink `constraint_0_power_limit_uw` and `constraint_1_power_limit_uw` under `/sys/devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0/`), plus read-only access (`0444`) to SMBIOS Type 17 memory entries (`/sys/firmware/dmi/entries/17-*/raw`) and unprivileged i915/xe GPU PMU engine counters (`perf_event_paranoid = 0`) for `lstats`.
2. **`/dev/input/` Dynamic Character Devices $\rightarrow$ Managed by `/etc/udev/rules.d/99-lenovo-input.rules`:**
   - **CRITICAL ARCHITECTURAL RULE:** NEVER use `tmpfiles.d` for `/dev/input/` nodes! Linux `systemd-tmpfiles` type `z` **does not follow symlinks** (`/dev/input/by-path/*` are symlinks; `tmpfiles.d` skips the underlying `/dev/input/eventX` targets).
   - `/etc/udev/rules.d/99-lenovo-input.rules` matches hardware by `ATTRS{name}` and `ENV{ID_INPUT_KEYBOARD}` at kernel probe time, setting mode `0666` on the actual character devices:
     - `ITE Tech. Inc. ITE Device(8258) Keyboard` $\rightarrow$ Copilot key (`0666`).
     - `Ideapad extra buttons` $\rightarrow$ Fn+R (240Hz/60Hz), Fn+L (Color Profiles), and Fn+N (`0666`).
     - `ENV{ID_INPUT_KEYBOARD}=="1"` $\rightarrow$ Built-in & external keyboards for zero-overhead `EVIOCGKEY` tap-vs-hold Copilot emulation via `lcopilot` (`0666`).

### Rule 3: Zero-Overhead, Event-Driven Architecture (Never Poll with Sleep)
* **Zero Polling Loops:** NEVER write `while true; do sleep ...; done` loops in background services or user scripts. Polling drains laptop battery and wastes CPU cycles.
* **Kernel Wait-Queue Blocking:** All background monitors must block inside the kernel wait queue using `select.poll()`:
  * `select.POLLPRI` for ACPI sysfs changes (woken up via kernel `sysfs_notify()`).
  * `select.POLLIN` for evdev hardware input events.
  * `select.POLLIN` on `NETLINK_KOBJECT_UEVENT` socket for zero-overhead DRM display hotplug/unplug events.
* **Unified Daemon:** All Legion OSD, hotkey events, and display hotplug monitoring are unified inside a single lightweight Python service: `~/.local/bin/legion-profile-osd` managed by `systemd --user` (`legion-profile-osd.service`). It is enabled only from `graphical-session.target`, dynamically recovers the KDE Wayland environment before launching GUI clients, and starts interactive commands in independent transient user scopes. CPU usage must remain at **0.0%** and memory under **10 MB**.

### Rule 4: Standardized Tooling Convention (`l*` Prefix in `~/.local/bin/`)
* All custom user-facing CLI tools reside in `~/.local/bin/` and use the **`l*`** prefix:
  * **`lbat`** $\rightarrow$ Battery Conservation Mode toggle (80% / 100%).
  * **`lmode`** $\rightarrow$ Power & Thermal profile manager (`quiet`, `balanced`, `perf`, `extreme`).
  * **`lhz`** $\rightarrow$ Display Refresh Rate toggle (240Hz $\leftrightarrow$ 60Hz) & Display Recovery (`lhz fix`).
  * **`lcolor`** $\rightarrow$ Native Display Color Profile manager with EDID panel matching (`sRGB`, `DisplayP3`, `DCIP3`, `AdobeRGB`, `REC709`, `Native`).
  * **`lstats`** $\rightarrow$ Hardware & Platform Telemetry CLI (Responsive 2×2 card TUI with interactive hotkeys including `[g]` Sparkline/Braille/Gauge trend view toggle, isolated forked NVML worker with D3cold idle backoff & GPU firmware version display, Intel i915/xe PMU + RAPL PP1 iGPU telemetry, SMBIOS Type 17 memory topology, per-SSD NVMe PCIe telemetry, per-connector GPU MUX routing, JSON/Watch/Short modes).
  * **`lcopilot`** $\rightarrow$ External keyboard & CLI trigger for Copilot Tap, Quick Launch menu, and Fn+N via `legion-profile-osd` UNIX datagram IPC.
  * **`test-hotkey`** $\rightarrow$ Standalone pure-Python evdev event sniffer.
* **Naming Safety:** NEVER shadow existing system binaries. (For example, `/usr/bin/bat` on Arch/CachyOS is a well-known `cat` clone with syntax highlighting; naming a script `bat` will break user workflows. Always use `lbat`).
* **English-Only Standardization:** All codebase assets (code, comments, docstrings, commit messages, CLI user output, help texts, and guides) MUST be strictly in English for public open-source readiness.
* **Strict Technical Grounding & Ban on Boastful Buzzwords (No "SoTA" / "State-of-the-Art"):**
  - NEVER use hyperbolic, boastful, or hype-driven buzzwords (e.g. `SoTA`, `SOTA`, `State-of-the-Art`, `state-of-the-art`, `revolutionary`, `game-changing`, `world-class`) in code, comments, docstrings, CLI output, help texts, documentation, commit messages, or agent responses.
  - Maintain a strictly grounded, objective, technical, and humble engineering tone across the entire repository. Technical merit is demonstrated through code quality, performance, and correctness, not self-praise.

### Rule 5: Visual Consistency, Feature-First Design & Asset Isolation
* **Feature-First & Honest Feedback Directive:**
  - OSD notifications and UI badges MUST strictly represent genuine, verified hardware/system state changes.
  - NEVER implement, retain, or praise "phantom" or "simulated" OSD feedback if the underlying hardware action or driver node is non-functional. Visuals serve real features, not illusions.
  - If a hardware feature lacks safe kernel driver support (e.g., the lid logo LED on Gen 10 lacking mainline sysfs exposure), either cleanly disable the notification or repurpose the hardware event hook to a verified, functional system feature.
* **Badge Aesthetics & Icons:**
  * Desktop OSD banners display dedicated high-resolution circular SVG badges matching exact hardware/feature states (`icons/*.svg`).
  * Active assets reside in: `~/.local/share/icons/legion/`
  * Repository assets are tracked in Git under `icons/`.

### Rule 6: Storage & Network Filesystem Integrity
* **Dual-boot NTFS Partitions (`/DATA1`, `/DATA2`):**
  * MUST use the modern in-kernel `ntfs` driver (introduced in Linux 7.1+ by Namjae Jeon).
  * Standard fstab options: `uid=1000,gid=1000,dmask=0022,fmask=0022,iocharset=utf8,windows_names,nofail 0 0`.
  * DO NOT install `ntfs-3g` as it creates a `/usr/bin/mount.ntfs` symlink that hijacks kernel mounts to FUSE.
  * DO NOT use `lazytime` or `force` on NTFS partitions holding large memory-mapped LLM models.
* **Router CIFS/SMB Network Shares (`lulu_home`):**
  * The router SMB server at `192.168.1.1` strictly requires `vers=2.0` (SMB 2.02). Omitting `vers=2.0` causes kernel error 22 (`EINVAL`).

### Rule 7: Hardware Safety & Constraints on Legion Gen 10
* **`custom` Mode Protection:** The EC rejects switching to `custom` with `-EINVAL 22` unless custom fan/power tables are preloaded. `lmode` must disable `custom` and display an English hint.
* **MMIO RAPL Synchronization (`intel-rapl-mmio:0`):** On Legion Pro 7 16IAX10H (Core Ultra 9 275HX), MSR RAPL (`intel-rapl:0`) is locked by BIOS (`enabled: 0`), while `processor_thermal_rapl` (`intel-rapl-mmio:0`) initializes at `30 W / 30 W` (`constraint_0` PL1 / `constraint_1` PL2) and is not updated by `lenovo_wmi_gamezone` when `platform_profile` changes. `legion_core.sync_rapl_mmio()` (invoked at startup, on `POLLPRI` `platform_profile` transitions, on `SUBSYSTEM=power_supply` netlink uevents in `legion-profile-osd`, and directly by `lmode`) synchronizes MMIO PL1/PL2 according to the active profile and AC/battery state (AC defaults: `low-power` `30W/30W`, `balanced` `45W/55W`, `performance` `55W/65W`, `max-power` `65W/85W`; battery cap: `30W/30W`; customizable via `"rapl_mmio"` in `config.jsonc` / `config.json`).
* **Fn + Q 3-Mode Loop:** The physical <kbd>Fn</kbd> + <kbd>Q</kbd> hardware key in firmware strictly cycles through 3 modes: **Quiet ➔ Balanced ➔ Performance**. `max-power` (Extreme) is an extended profile switched directly via `lmode extreme`.
* **Fn + R Keycode:** The physical <kbd>Fn</kbd> + <kbd>R</kbd> shortcut emits scancode `0x0110`, translated by `ideapad_laptop` to **Keycode `562` (`KEY_REFRESH_RATE_TOGGLE`)** on `/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event`.
* **Fn + L (Display Color Profile Cycler — Repurposed):** The physical <kbd>Fn</kbd> + <kbd>L</kbd> shortcut emits scancodes `0x012c` / `0x012b` (Keycode `240`) on `VPC2004`. Because the mainline Linux kernel lacks a safe sysfs interface for physical lid logo control on Gen 10, and out-of-tree DKMS modules introduce severe throttling risks (issues #491 and #585), the fake logo OSD has been eliminated. The key has been repurposed as a **Display Color Profile Cycler** via `lcolor cycle` (configurable via `fn_l` in `~/.config/legion/config.json`).
  - **Strict Scancode Matching:** The in-kernel `ideapad_laptop` driver translates all unmapped VPC events to Keycode `240` (`KEY_UNKNOWN_VPC`), which includes:
    * **Keyboard Backlight Brightness Levels (Fn+Up/Down):** `0x0118` (Level 0 / Off), `0x0119` (Level 1 / Low), `0x011a` (Level 2 / Medium), `0x0126` (Level 3 / Max).
    * **Keyboard RGB Backlight Profiles (Fn+Space):** `0x0120` (Preset 1) through `0x0125` (Preset 6).
    * **Fn+L (Repurposed):** `0x012c` (Logo On) and `0x012b` (Logo Off).
    Background daemons MUST strictly filter Fn+L by hardware scancodes (`0x012c`, `0x012b`) via `EV_MSC` and immediately reset pending scancodes upon event consumption/synchronization, preventing false triggers when keyboard backlight or RGB profile shortcuts are pressed.
  - **Strict Panel Matching Guard:** `lcolor` reads the internal eDP EDID (`/sys/class/drm/*-eDP-*/edid`) and verifies that the hardware ID matches `SDC420B` before applying factory-calibrated profiles (`sRGB`, `DisplayP3`, `DCIP3`, `AdobeRGB`, `REC709`, `Native`). If a mismatched panel is detected, it safely halts with an informative warning.
* **Fn + N (Smart Window Dispatcher & Launcher):** Emits Keycode `618` (scancode `0x012a`) on `VPC2004:00-event`. The original firmware action ("device info") has no Linux counterpart. Hooked by `legion-profile-osd` via an Action Dispatcher supporting `toggle` (smart Wayland window-aware lifecycle management via KWin DBus scripting) or `exec` (direct execution).
  - **Smart Window Management (KDE Plasma 6 Wayland):**
    - If not running $\rightarrow$ launches `exec` (default: `alacritty -e nvtop`).
    - If running but obscured/minimized $\rightarrow$ resolves the process tree (including terminal wrapper PIDs) and **brings window to front & focuses it** instead of killing it.
    - If running and already active in foreground $\rightarrow$ dispatches `on_active`: `"close"` (default: cleanly terminates process to eliminate background GPU/CPU polling), `"minimize"`, or `"none"`.
  - **JSONC Config Support:** Configured via `~/.config/legion/config.jsonc` (or `config.json`), with native comment (`//`, `/* */`) and trailing comma support. Template available at `config/config.example.jsonc`.
* **Copilot Key (Smart Terminal Summon & Candidate Launcher):** Emits Keycode `193` (`KEY_F23`) via `ITE Device(8258)`:
  - **Short Tap (< 0.3s):** Dispatches `copilot_tap` (defaults to `"action": "smart_terminal"` with `alacritty`).
    - Inspects running instances: verifies direct child process is a valid login shell from `/etc/shells` and idle at prompt via POSIX foreground process group (`tpgid == shell_pid`), cleanly ignoring non-shell applications (`nvtop`, `vim`, `paru`).
    - If an idle terminal exists: brings the most recently active idle window to front in KWin 6 stacking order without spawning duplicates or interrupting active text input. If already focused, preserves focus.
    - If all terminals are busy (e.g. running `paru`, `vim`, `python`, `llama-server`) or none open: spawns a fresh terminal running `lstats`, then cleanly transitions to the interactive shell prompt, with 1.2s debounce protection against rapid spamming.
  - **Long Hold (>= 0.3s):** Opens the Legion Candidate Picker menu (Rofi / Kdialog fallback).
  - **External Keyboard Dual-Action Emulation (`lcopilot` / `copilot_auto` IPC):** Invoking `lcopilot` (or `lcopilot auto` / `lcopilot menu` bound to a KDE shortcut such as `Meta+M`) queries `EVIOCGKEY` across readable `/dev/input/event*` keyboard nodes at `t = 0` and blocks in the kernel wait queue via `select.poll()` for up to `280ms`: if the held key is released before `280ms`, it triggers `copilot_tap`; if still held at `280ms` (or double-pressed within `380ms` when no key is held), it opens the Quick Launch candidate menu; if the menu is already open, it dismisses it immediately.
* **Fn + C (Hardware SIGINT / Break):** Emitted directly by the `ITE Device(8258)` keyboard controller as a hardware macro sending `KEY_LEFTCTRL` (`29`) + `KEY_C` (`46`), generating standard terminal `^C` (SIGINT) to interrupt or abort active foreground CLI tasks (e.g. `lstats -w`, shell scripts).
* **Display Hotplug & Plasma 6 Backlight Recovery:**
  - **KDE Plasma 6 Backlight Binding Bug:** When external monitors (especially via USB-C to HDMI adapters) disconnect, KDE Plasma 6's PowerDevil brightness controller frequently loses the active backlight device binding, disabling hardware brightness keys and slider control.
  - **Netlink Hotplug Listener & Sleep Guard:** `legion-profile-osd` listens to kernel DRM hotplug uevents via `NETLINK_KOBJECT_UEVENT`.
  - **DPMS & Screen Lock Guard:** When displays enter DPMS sleep (e.g. idle after 600s), USB-C adapters may drop HPD, causing spurious DRM disconnect events. Restarting PowerDevil while sleeping/locked wakes up the monitors, causing an infinite 10-minute wake loop. The daemon checks `is_display_sleeping()` (filtering strictly on `status == "connected"` connectors in `/sys/class/drm/*-eDP-*/dpms` to avoid disconnected phantom connectors like `card0-eDP-2`) and `is_session_locked()` via `org.freedesktop.ScreenSaver`.
  - **Deferred Wake Recovery:** If an external display disconnect occurs while the screen is asleep or locked, recovery is deferred (`_deferred_drm_recovery = True`). When the system wakes and unlocks, if the external display is genuinely disconnected, `handle_drm_hotplug(force=True)` restarts PowerDevil; if the external display reconnected or was simply waking from DPMS standby, deferred recovery is cleared without disrupting the user.
  - **Internal Display Isolation & Clamshell External Fallback (`get_internal_display()` & `lhz`):** `lcolor` strictly targets the internal `SDC420B` eDP panel (even when disabled in clamshell/external-only mode, queuing the profile in standby without touching external monitors). `lhz` targets the internal eDP panel (`240Hz <-> 60Hz`) whenever enabled, and automatically falls back to cycling available refresh rates at the active resolution on the primary external monitor when the internal panel is disabled (`lhz fix` also guards against all-outputs-disabled lockouts, 0-brightness traps, and polls PowerDevil DBus integer readiness across `intel_backlight` / `nvidia_*`).
  - **EDID CTA-861 / DisplayID Multi-Block Parser:** `parse_edid()` in `legion_core.py` scans across the full EDID payload for `0xFC` (Display Product Name) before `0xFE` (Alphanumeric String), correctly parsing pre-DTD regions (CTA-861 byte 132), detailed timing descriptors, and multi-block extensions (CTA 1.4a/DisplayID).
  - **Purge of Legacy Workaround (`powerdevil-resume-watch`):** An older standalone shell script and user service (`powerdevil-resume-watch.sh` / `powerdevil-resume-watch.service`) previously intercepted `org.freedesktop.login1` `PrepareForSleep (false)` to bounce PowerDevil unconditionally on system resume. Because it lacked DPMS standby and session lock guards, it risked waking displays during unattended sleep cycles. It has been fully purged, stopped, disabled, and superseded by `legion-profile-osd`'s zero-overhead, event-driven DRM Netlink listener and guarded deferred wake recovery.

---

## 3. System Architecture & File Directory Map

### A. System Deployment Map
```text
/ (System Root)
├── etc/
│   ├── tmpfiles.d/
│   │   ├── lenovo_conservation.conf       # 0666 on /sys/bus/platform/devices/VPC2004:00/conservation_mode
│   │   ├── lenovo_platform_profile.conf   # 0666 on /sys/firmware/acpi/platform_profile
│   │   └── lenovo_rapl_mmio.conf          # 0666 on intel-rapl-mmio:0 PL1/PL2 limit nodes
│   └── udev/
│       └── rules.d/
│           └── 99-lenovo-input.rules      # 0666 on dynamic /dev/input/ character devices
└── home/quangtm/
    ├── .config/
    │   ├── legion/
    │   │   └── config.json               # Hotkey dispatcher & candidate picker configuration
    │   └── systemd/
    │       └── user/
    │           └── legion-profile-osd.service # Systemd user service (active, 0% CPU)
    └── .local/
        ├── bin/
        │   ├── lbat                      # Sudo-less battery conservation CLI (~80% / 100%)
        │   ├── lmode                     # Adaptive power & thermal manager with live fan RPMs
        │   ├── lhz                       # Display refresh rate toggle (240Hz / 60Hz)
        │   ├── lcolor                    # Display color profile manager with EDID panel check
        │   ├── lstats                    # Hardware & Platform Telemetry CLI (Live dashboard)
        │   ├── lcopilot                  # External keyboard / CLI trigger for Copilot & Quick Launch
        │   ├── legion_core.py            # Consolidated hardware & platform core library
        │   ├── legion-profile-osd        # Unified event-driven daemon (Fn+Q, Fn+R, Fn+L, Fn+N, Copilot)
        │   └── test-hotkey               # Pure-Python hardware hotkey discovery sniffer
        └── share/
            ├── applications/
            │   ├── legion-copilot-tap.desktop   # KDE shortcut entry for Copilot Tap
            │   └── legion-copilot-menu.desktop  # KDE shortcut entry for Quick Launch menu
            ├── color/
            │   └── icc/                  # Factory-calibrated ICC color profiles (SDC420B)
            └── icons/
                └── legion/               # High-res circular SVG badges
```

### B. Repository Structure (`legion-linux-toolkit`)
```text
/DATA1/quang_dev/legion-linux-toolkit/
├── .agents/
│   └── AGENTS.md                         # Authoritative architectural directives (this file)
├── AGENTS.md                             # AI Developer Gateway pointer
├── bin/                                  # CLI scripts deployed to ~/.local/bin/
├── color-profiles/                       # Factory ICC profiles and calibration reports
├── desktop/                              # Desktop entry source for lhz-toggle
├── docs/                                 # Hardware guides and technical documentation
├── icons/                                # SVG badges deployed to ~/.local/share/icons/legion/
├── install.sh                            # Automated deployment & permission setup script
├── systemd/                              # User service definition
├── tmpfiles.d/                           # Sysfs permission configurations for /etc/tmpfiles.d/
└── udev/                                 # Udev rules for /etc/udev/rules.d/
```

---

## 4. Operational Directives for Future Agents

1. **Before modifying any hardware script:** Review the respective hardware section in `docs/` and this `AGENTS.md`.
2. **When adding a new hardware toggle:** Follow the 3-step pattern:
   - Step 1: Grant permissions via `/etc/tmpfiles.d/*.conf` (sysfs) or `/etc/udev/rules.d/` (input devices).
   - Step 2: Implement the CLI script in `~/.local/bin/l<name>`.
   - Step 3: Wire into `legion-profile-osd` if hardware event hooks or OSD banners are required.
3. **Always preserve documentation integrity:** Any modifications made to scripts, configs, or services must be synchronously documented in this `AGENTS.md`.
