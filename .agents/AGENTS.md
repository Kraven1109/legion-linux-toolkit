# AGENTS.md — Architectural Directives & Design Philosophy

> **Target Environment:** Lenovo Legion Pro 7 16IAX10H (Type `83F5`, BIOS `Q7CN78WW`)  
> **Operating System:** CachyOS Linux (Kernel 7.2+, KDE Plasma 6 Wayland, Dual-boot with Windows 11)  
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
* **NO Third-Party Helper Apps or Bloat:** Never suggest or install third-party GUI or CLI bloat (e.g. OpenRGB, Vantage clones, third-party background pollers) unless explicitly demanded by the user.
* **Kernel & Native First:** Always exploit existing in-kernel platform drivers (`ideapad_laptop`, `lenovo_wmi`, in-kernel `ntfs`), native sysfs interfaces, and native desktop compositors (`kscreen-doctor`, `notify-send`, `qdbus6`).

### Rule 2: Strict Permission Architecture (`/etc/tmpfiles.d/` for `/sys/`, `/etc/udev/rules.d/` for `/dev/input/`)
To ensure 100% sudo-less operation that persists across reboots without breaking, permissions MUST strictly adhere to this architectural boundary:
1. **`/sys/` Static Sysfs Nodes $\rightarrow$ Managed by `/etc/tmpfiles.d/*.conf`:**
   - `/etc/tmpfiles.d/lenovo_conservation.conf` $\rightarrow$ Battery charge cap (`0666` on `conservation_mode` for `lbat`).
   - `/etc/tmpfiles.d/lenovo_platform_profile.conf` $\rightarrow$ Power & thermal profiles (`0666` on `platform_profile` for `lmode` & Fn+Q).
2. **`/dev/input/` Dynamic Character Devices $\rightarrow$ Managed by `/etc/udev/rules.d/99-lenovo-input.rules`:**
   - **CRITICAL ARCHITECTURAL RULE:** NEVER use `tmpfiles.d` for `/dev/input/` nodes! Linux `systemd-tmpfiles` type `z` **does not follow symlinks** (`/dev/input/by-path/*` are symlinks; `tmpfiles.d` skips the underlying `/dev/input/eventX` targets).
   - `/etc/udev/rules.d/99-lenovo-input.rules` matches hardware by `ATTRS{name}` at kernel probe time, setting mode `0666` on the actual character devices:
     - `ITE Tech. Inc. ITE Device(8258) Keyboard` $\rightarrow$ Copilot key (`0666`).
     - `Ideapad extra buttons` $\rightarrow$ Fn+R (240Hz/60Hz) & Fn+L (Logo LED) (`0666`).

### Rule 3: Zero-Overhead, Event-Driven Architecture (Never Poll with Sleep)
* **Zero Polling Loops:** NEVER write `while true; do sleep ...; done` loops in background services or user scripts. Polling drains laptop battery and wastes CPU cycles.
* **Kernel Wait-Queue Blocking:** All background monitors must block inside the kernel wait queue using `select.poll()`:
  * `select.POLLPRI` for ACPI sysfs changes (woken up via kernel `sysfs_notify()`).
  * `select.POLLIN` for evdev hardware input events.
* **Unified Daemon:** All Legion OSD and hotkey events are unified inside a single lightweight Python service: `~/.local/bin/legion-profile-osd` managed by `systemd --user` (`legion-profile-osd.service`). CPU usage must remain at **0.0%** and memory under **10 MB**.

### Rule 4: Standardized Tooling Convention (`l*` Prefix in `~/.local/bin/`)
* All custom user-facing CLI tools reside in `~/.local/bin/` and use the **`l*`** prefix:
  * **`lbat`** $\rightarrow$ Battery Conservation Mode toggle (80% / 100%).
  * **`lmode`** $\rightarrow$ Power & Thermal profile manager (`quiet`, `balanced`, `perf`, `extreme`).
  * **`lhz`** $\rightarrow$ Display Refresh Rate toggle (240Hz $\leftrightarrow$ 60Hz).
  * **`lcolor`** $\rightarrow$ Native Display Color Profile manager with EDID panel matching (`sRGB`, `DisplayP3`, `DCIP3`, `AdobeRGB`, `REC709`, `Native`).
  * **`test-hotkey`** $\rightarrow$ Standalone pure-Python evdev event sniffer.
* **Naming Safety:** NEVER shadow existing system binaries. (For example, `/usr/bin/bat` on Arch/CachyOS is a well-known `cat` clone with syntax highlighting; naming a script `bat` will break user workflows. Always use `lbat`).
* **English-Only Standardization:** All codebase assets (code, comments, docstrings, commit messages, CLI user output, help texts, and guides) MUST be strictly in English for public open-source readiness.

### Rule 5: Visual Consistency, Feature-First Design & Asset Isolation
* **Feature-First & Honest Feedback Directive:**
  - OSD notifications and UI badges MUST strictly represent genuine, verified hardware/system state changes.
  - NEVER implement, retain, or praise "phantom" or "simulated" OSD feedback if the underlying hardware action or driver node is non-functional. Visuals serve real features, not illusions.
  - If a hardware feature lacks safe kernel driver support (e.g. lid logo LED on Gen 10 lacking mainline sysfs exposure), either cleanly disable the notification or repurpose the hardware event hook to a verified, functional system feature.
* **Badge Aesthetics & Icons:**
  * Desktop OSD banners display dedicated high-resolution circular SVG badges matching exact hardware/feature states (`icons/*.svg`).
  * Active assets reside in: `~/.local/share/icons/legion/`
  * Repository assets managed via Git/GitHub.

### Rule 6: Storage & Network Filesystem Integrity
* **Dual-boot NTFS Partitions (`/DATA1`, `/DATA2`):**
  * MUST use the modern in-kernel `ntfs` driver (introduced in Linux 7.1+ by Namjae Jeon).
  * Standard fstab options: `uid=1000,gid=1000,dmask=0022,fmask=0022,iocharset=utf8,windows_names,nofail 0 0`.
  * DO NOT install `ntfs-3g` as it creates a `/usr/bin/mount.ntfs` symlink that hijacks kernel mounts to FUSE.
  * DO NOT use `lazytime` or `force` on NTFS partitions holding large memory-mapped LLM models.
* **Router CIFS/SMB Network Shares (`lulu_home`):**
  * Router SMB server at `192.168.1.1` strictly requires `vers=2.0` (SMB 2.02). Omitting `vers=2.0` causes kernel error 22 (EINVAL).

### Rule 7: Hardware Safety & Constraints on Legion Gen 10
* **`custom` Mode Protection:** The EC rejects switching to `custom` with `-EINVAL 22` unless custom fan/power tables are preloaded. `lmode` must disable `custom` and display an English hint.
* **Fn + Q 3-Mode Loop:** The physical <kbd>Fn</kbd> + <kbd>Q</kbd> hardware key in firmware strictly cycles through 3 modes: **Quiet ➔ Balanced ➔ Performance**. `max-power` (Extreme) is an extended profile switched directly via `lmode extreme`.
* **Fn + R Keycode:** The physical <kbd>Fn</kbd> + <kbd>R</kbd> shortcut emits scancode `0x0110`, translated by `ideapad_laptop` to **Keycode `562` (`KEY_REFRESH_RATE_TOGGLE`)** on `/dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event`.
* **Fn + L (Display Color Profile Cycler — Repurposed):** The physical <kbd>Fn</kbd> + <kbd>L</kbd> shortcut emits scancodes `0x012c` / `0x012b` (Keycode `240`) on `VPC2004`. Because Linux mainline lacks a safe sysfs interface for physical lid logo control on Gen 10 and out-of-tree DKMS modules introduce severe throttling risks (issues #491, #585), fake logo OSD is eliminated. Repurposed to **Display Color Profile Cycler** via `lcolor cycle` (configurable via `fn_l` in `~/.config/legion/config.json`).
  - **Strict Panel Matching Guard:** `lcolor` reads the internal eDP EDID (`/sys/class/drm/*-eDP-*/edid`) and verifies the hardware ID matches `SDC420B` before applying factory-calibrated profiles (`sRGB`, `DisplayP3`, `DCIP3`, `AdobeRGB`, `REC709`, `Native`). If a mismatched panel is detected, it safely halts with an informative warning.
* **Copilot Key (Native Hotkey Dispatcher):** Emits hardware macro `LeftMeta (125) + LeftShift (42) + F23 (193)` via `ITE Device(8258)`. Hooked natively by `legion-profile-osd` on Keycode `193` with zero polling. Tap (<0.3s) → default terminal; Hold (≥0.3s) → rofi candidate picker (`✦ Quick Launch`, kdialog fallback); Hold again → dismiss menu. Configurable via `~/.config/legion/config.json`. Permissions: `/etc/udev/rules.d/99-lenovo-input.rules`.
* **Fn + N (Configurable Action Dispatcher):** Emits Keycode `618` (scancode `0x012a`) on `VPC2004:00-event`. Original firmware action ("device info") is useless on Linux. Hooked by `legion-profile-osd` via an Action Dispatcher supporting `toggle` (process-lifecycle management via `process`) or `exec` (direct execution). Default: toggle `alacritty -e nvtop` with process `nvtop`. Configurable via `fn_n` in `~/.config/legion/config.json`.

---

## 3. System Architecture & File Directory Map

```text
/home/quangtm/
├── .local/
│   ├── bin/
│   │   ├── lbat                      # Sudo-less battery conservation CLI (~80% / 100%)
│   │   ├── lmode                     # Adaptive power & thermal manager with live fan RPMs
│   │   ├── lhz                       # Display refresh rate toggle (240Hz / 60Hz)
│   │   ├── lcolor                    # Display color profile manager with EDID panel check
│   │   ├── legion-profile-osd        # Unified event-driven daemon (Fn+Q, Fn+R, Fn+L, Fn+N, Copilot)
│   │   └── test-hotkey               # Pure-Python hardware hotkey discovery sniffer
│   └── share/
│       ├── applications/
│       │   └── lhz-toggle.desktop    # Desktop entry for KDE shortcut integration
│       ├── color/
│       │   └── icc/                  # Factory-calibrated ICC color profiles (SDC420B)
│       └── icons/
│           └── legion/               # High-res circular SVG badges
├── .config/
│   └── systemd/
│       └── user/
│           └── legion-profile-osd.service # Systemd user service (active, 0% CPU)
├── /etc/
│   └── tmpfiles.d/
│       ├── lenovo_conservation.conf       # 0666 on /sys/bus/platform/devices/VPC2004:00/conservation_mode
│       ├── lenovo_platform_profile.conf   # 0666 on /sys/firmware/acpi/platform_profile
│       └── lenovo_hotkeys.conf            # 0666 on /dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event
└── docs/                                  # Comprehensive hardware guides & documentation
```

---

## 4. Operational Directives for Future Agents

1. **Before modifying any hardware script:** Review the respective hardware section in `docs/` and this `AGENTS.md`.
2. **When adding a new hardware toggle:** Follow the 3-step pattern:
   - Step 1: Grant permissions via `/etc/tmpfiles.d/*.conf` (sysfs) or `udev` (input devices).
   - Step 2: Implement CLI script in `~/.local/bin/l<name>`.
   - Step 3: Wire into `legion-profile-osd` if hardware event hooks or OSD banners are required.
3. **Always preserve documentation integrity:** Any modifications made to scripts, configs, or services must be synchronously documented in `AGENTS.md`.
