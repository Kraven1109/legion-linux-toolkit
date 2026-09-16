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

2. **Unified Sudo-less Strategy via `/etc/tmpfiles.d/`:**
   - ALL hardware permissions reside in `/etc/tmpfiles.d/*.conf`:
     - `lenovo_conservation.conf` $\rightarrow$ `conservation_mode` (`lbat`)
     - `lenovo_platform_profile.conf` $\rightarrow$ `platform_profile` (`lmode` / Fn+Q)
     - `lenovo_hotkeys.conf` $\rightarrow$ `pci-0000:00:1f.0-platform-VPC2004:00-event` (`lhz` / Fn+R)
   - Never use ad-hoc root scripts or polling wrappers.

3. **Zero-Overhead Event-Driven Architecture (NO Polling Loops):**
   - NEVER write `while sleep` loops. All background services must sleep inside kernel wait queues via `select.poll()`.
   - Unified daemon runs as a user service: `systemctl --user status legion-profile-osd.service` (0% CPU).

4. **Standardized Tooling Convention (`l*` Prefix in `bin/`):**
   - All custom CLI tools use the **`l*`** prefix (`lbat`, `lmode`, `lhz`, `test-hotkey`).
   - NEVER shadow system binaries (e.g. `/usr/bin/bat` is an Arch syntax highlighter; custom scripts must use `lbat`).

5. **Visual Consistency & Cloud Backup:**
   - Notifications use 64x64 circular SVG badges matching exact hardware LED states (`icons/*.svg`).
   - Synced to OneDrive at `~/OneDrive/CloudSync/Software/16iax10h-power-icons/`.

6. **Storage & Network Integrity:**
   - NTFS mounts (`/DATA1`, `/DATA2`) MUST use the modern in-kernel `ntfs` driver. NEVER install `ntfs-3g`.
   - Router CIFS mounts (`lulu_home`) strictly require `vers=2.0`.

7. **Hardware Constraints on Legion Gen 10:**
   - `custom` profile is disabled on Linux (EC returns `-EINVAL 22`).
   - Physical <kbd>Fn</kbd> + <kbd>Q</kbd> cycles strictly 3 modes: **Quiet ➔ Balanced ➔ Performance**.
   - Physical <kbd>Fn</kbd> + <kbd>R</kbd> emits **Keycode `562` (`KEY_REFRESH_RATE_TOGGLE`)**.
   - Physical <kbd>Fn</kbd> + <kbd>L</kbd> toggles logo light (scancodes `0x012c` ON / `0x012b` OFF on VPC2004) with native OSD.
   - Physical Copilot key emits `Meta + Shift + F23` on `event4`; bind natively in KDE Shortcuts (no third-party bloat).

---

## 📂 Project Structure

* **`bin/`**: Core CLI tools (`lbat`, `lmode`, `lhz`, `legion-profile-osd`, `test-hotkey`).
* **`systemd/`**: User service definition (`legion-profile-osd.service`).
* **`tmpfiles.d/`**: Boot-time permission configs for `/etc/tmpfiles.d/`.
* **`icons/`**: 5 high-res circular SVG badges for OSD notifications.
* **`desktop/`**: KDE desktop shortcut entry for `lhz toggle`.
* **`docs/`**: Comprehensive hardware guides and mount documentation.
* **`install.sh`**: 1-click installer and deployer.

For full architectural details, consult [.agents/AGENTS.md](.agents/AGENTS.md).
