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
  * **`test-hotkey`** $\rightarrow$ Standalone pure-Python evdev event sniffer.
* **Naming Safety:** NEVER shadow existing system binaries. (For example, `/usr/bin/bat` on Arch/CachyOS is a well-known `cat` clone with syntax highlighting; naming a script `bat` will break user workflows. Always use `lbat`).

### Rule 5: Visual Consistency & Asset Isolation
* Desktop OSD banners must display dedicated high-resolution circular SVG badges matching exact hardware states:
  * 🔵 Quiet Mode $\rightarrow$ `quiet.svg` (Blue LED)
  * ⚪ Balanced Mode $\rightarrow$ `balanced.svg` (White LED)
  * 🔴 Performance Mode $\rightarrow$ `performance.svg` (Red LED)
  * 🟣 Extreme Mode $\rightarrow$ `extreme.svg` (Purple LED)
  * ⚙️ Custom Mode $\rightarrow$ `custom.svg` (Teal)
* **Asset Location & Cloud Backup:**
  * Active assets reside in: `~/.local/share/icons/legion/`
  * Permanent cloud backups reside in: `~/OneDrive/CloudSync/Software/16iax10h-power-icons/`
  * Fresh installs can be restored with a single command: `~/OneDrive/CloudSync/Software/16iax10h-power-icons/install.sh`.

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
* **Fn + L (Logo Light):** The physical <kbd>Fn</kbd> + <kbd>L</kbd> hardware key is fully operational on Gen 10! The EC toggles the back lid logo light and reports alternating scancodes `0x012c` (ON) and `0x012b` (OFF) on `VPC2004:00-event`. Integrated into `legion-profile-osd` for visual OSD feedback.
* **Copilot Key (Native Hotkey Dispatcher):** Emits hardware macro `LeftMeta (125) + LeftShift (42) + F23 (193)` via `ITE Device(8258)`. Hooked natively by `legion-profile-osd` on Keycode `193` with zero polling. Configurable dynamically via `~/.config/legion/config.json` (defaults to Alacritty). Hardware permissions managed via `/etc/udev/rules.d/99-lenovo-keyboard.rules`.

---

## 3. System Architecture & File Directory Map

```text
/home/quangtm/
├── .local/
│   ├── bin/
│   │   ├── lbat                      # Sudo-less battery conservation CLI (~80% / 100%)
│   │   ├── lmode                     # Adaptive power & thermal manager with live fan RPMs
│   │   ├── lhz                       # Display refresh rate toggle (240Hz / 60Hz)
│   │   ├── legion-profile-osd        # Unified event-driven daemon (Fn+Q, Fn+R, OSD)
│   │   └── test-hotkey               # Pure-Python hardware hotkey discovery sniffer
│   └── share/
│       ├── applications/
│       │   └── lhz-toggle.desktop    # Desktop entry for KDE shortcut integration
│       └── icons/
│           └── legion/               # 5 circular SVG badges (quiet, balanced, perf, extreme, custom)
├── .config/
│   └── systemd/
│       └── user/
│           └── legion-profile-osd.service # Systemd user service (active, 0% CPU)
├── /etc/
│   └── tmpfiles.d/
│       ├── lenovo_conservation.conf       # 0666 on /sys/bus/platform/devices/VPC2004:00/conservation_mode
│       ├── lenovo_platform_profile.conf   # 0666 on /sys/firmware/acpi/platform_profile
│       └── lenovo_hotkeys.conf            # 0666 on /dev/input/by-path/pci-0000:00:1f.0-platform-VPC2004:00-event
└── OneDrive/
    └── CloudSync/
        └── Software/
            ├── AGENTS.md                          # [THIS FILE] Core architectural directives
            ├── Legion_Pro_7_16IAX10H_Hardware_Guide.md # Comprehensive hardware reference manual
            ├── Legion_16IAX10H_Battery_Conservation_CachyOS.md # Battery guide
            ├── CachyOS_NTFS_Mount_Guide.md        # NTFS kernel driver & CIFS mount guide
            └── 16iax10h-power-icons/              # Permanent cloud backup of all SVG badges + install.sh
```

---

## 4. Operational Directives for Future Agents

1. **Before modifying any hardware script:** Review the respective section in [Legion_Pro_7_16IAX10H_Hardware_Guide.md](file:///home/quangtm/OneDrive/CloudSync/Software/Legion_Pro_7_16IAX10H_Hardware_Guide.md).
2. **When adding a new hardware toggle:** Follow the 3-step pattern:
   - Step 1: Grant permissions via `/etc/tmpfiles.d/*.conf`.
   - Step 2: Implement CLI script in `~/.local/bin/l<name>`.
   - Step 3: Wire into `legion-profile-osd` if hardware event hooks or OSD banners are required.
3. **Always preserve documentation integrity:** Any modifications made to scripts, configs, or services must be synchronously documented in both `Legion_Pro_7_16IAX10H_Hardware_Guide.md` and this `AGENTS.md`.
