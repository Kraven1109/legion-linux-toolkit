# AGENTS.md — Universal AI Developer Directives

> **Primary Full Specification:** See [.agents/AGENTS.md](file:///.agents/AGENTS.md) for the complete hardware reference and detailed operational guidelines.  
> **Target System:** Lenovo Legion Pro 7 16IAX10H (CachyOS Linux Kernel 7.2+, KDE Plasma 6 Wayland, Dual-boot with Windows 11).  
> **Compatibility:** Compatible with Antigravity, GitHub Copilot, KiloCode, Cursor, Claude Code, and all standard AI coding assistants.

---

## ⚡ Quick Directives for Any AI Agent Working Here

Every AI developer, agent, or automated workflow operating in this workspace **MUST adhere to these 7 Golden Rules**:

1. **100% Native & Zero Bloat (NO OpenRGB / NO Vantage Clones):**
   - Do NOT install or suggest third-party RGB/Vantage tools.
   - Use Linux in-kernel drivers, ACPI/sysfs interfaces, and native desktop compositors (`kscreen-doctor`, `notify-send`).

2. **Strict Permission Architecture (`/etc/tmpfiles.d/` for `/sys/`, udev for `/dev/input/`):**
   - **`/sys/` nodes $\rightarrow$ `/etc/tmpfiles.d/*.conf`:** `lenovo_conservation.conf` (`lbat`), `lenovo_platform_profile.conf` (`lmode` / Fn+Q).
   - **`/dev/input/` nodes $\rightarrow$ `/etc/udev/rules.d/99-lenovo-input.rules`:** DO NOT use tmpfiles.d for evdev (symlink trap). Udev matches `ATTRS{name}` for ITE Keyboard (Copilot) & Ideapad extra buttons (Fn+R, Fn+L) at `0666`.

3. **Zero-Overhead Event-Driven Architecture (NO Polling Loops):**
   - NEVER write `while sleep` loops. All background services must sleep inside kernel wait queues via `select.poll()`.
   - Unified daemon runs as a user service: `systemctl --user status legion-profile-osd.service` (0% CPU).

4. **Standardized Tooling Convention (`l*` Prefix in `bin/`) & English-Only:**
   - All custom CLI tools use the **`l*`** prefix (`lbat`, `lmode`, `lhz`, `lcolor`, `test-hotkey`).
   - NEVER shadow system binaries (e.g. `/usr/bin/bat` is an Arch syntax highlighter; custom scripts must use `lbat`).
   - **English-Only Standardization:** All code, comments, docstrings, commit messages, CLI user-facing output, and documentation MUST be written in English for public readiness.

5. **Visual Consistency & Feature-First Design:**
   - **Feature-First & Honest Feedback Directive:** OSD notifications and UI badges MUST strictly represent genuine, verified hardware/system state changes. NEVER implement or praise "phantom" or "simulated" OSD feedback if the underlying hardware action or driver node is non-functional.
   - Notifications use 64x64 circular SVG badges matching exact hardware/feature states (`icons/*.svg`). Managed via Git/GitHub.

6. **Storage & Network Integrity:**
   - NTFS mounts (`/DATA1`, `/DATA2`) MUST use the modern in-kernel `ntfs` driver. NEVER install `ntfs-3g`.
   - Router CIFS mounts (`lulu_home`) strictly require `vers=2.0`.

7. **Hardware Constraints on Legion Gen 10:**
   - `custom` profile is disabled on Linux (EC returns `-EINVAL 22`).
   - Physical <kbd>Fn</kbd> + <kbd>Q</kbd> cycles strictly 3 modes: **Quiet ➔ Balanced ➔ Performance**.
   - Physical <kbd>Fn</kbd> + <kbd>R</kbd> emits **Keycode `562` (`KEY_REFRESH_RATE_TOGGLE`)**.
   - Physical <kbd>Fn</kbd> + <kbd>L</kbd> emits scancodes `0x012c` / `0x012b` (Keycode `240`) on `VPC2004`. Because Gen 10 lacks a mainline sysfs interface for the logo LED and third-party DKMS modules introduce severe throttling risks (issues #491, #585), fake logo OSD is eliminated. Repurposed to **Display Color Profile Cycler** via `lcolor cycle` (configurable via `fn_l` in `~/.config/legion/config.json`).
   - Physical Copilot key emits Keycode `193` on ITE Keyboard; hooked natively by `legion-profile-osd` (config-driven in `~/.config/legion/config.json`). Tap (<0.3s) launches default terminal; Hold (≥0.3s) opens Rofi menu (`✦ Quick Launch`); Hold again dismisses menu.
   - Physical <kbd>Fn</kbd> + <kbd>N</kbd> emits Keycode `618` (scancode `0x012a`) on VPC2004; default "device info" action repurposed as configurable action launcher (Action Dispatcher supporting `toggle` via `process` or `exec` in `fn_n`, default: toggle `alacritty -e nvtop`).

---

## 📂 Project Structure

* **`bin/`**: Core CLI tools (`lbat`, `lmode`, `lhz`, `lcolor`, `legion-profile-osd`, `test-hotkey`).
* **`color-profiles/`**: Factory-calibrated ICC profiles & Dolby Vision config for Samsung OLED (`SDC420B`).
* **`systemd/`**: User service definition (`legion-profile-osd.service`).
* **`tmpfiles.d/`**: Boot-time permission configs for `/etc/tmpfiles.d/`.
* **`icons/`**: High-res circular SVG badges for OSD notifications.
* **`desktop/`**: KDE desktop shortcut entry for `lhz toggle`.
* **`docs/`**: Comprehensive hardware guides and mount documentation.
* **`install.sh`**: 1-click installer and deployer.

For full architectural details, consult [.agents/AGENTS.md](.agents/AGENTS.md).
