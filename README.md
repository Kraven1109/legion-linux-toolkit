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
| **`lbat`** | Battery Conservation Mode | `status`, `on` (~80% cap), `off` (100% full), `toggle` |
| **`lmode`** | Power & Thermal Manager | `status`, `next` (Fn+Q loop), `quiet`, `balanced`, `perf`, `extreme` |
| **`lhz`** | Display Refresh Rate | `status`, `toggle` (240Hz $\leftrightarrow$ 60Hz), `240`, `60` |
| **`test-hotkey`** | Hardware Event Sniffer | Real-time evdev scancode & keycode diagnostic tool |

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
├── .agents/
│   └── AGENTS.md            # Comprehensive AI developer directives & hardware rules
├── AGENTS.md                # Universal root wrapper for Copilot, KiloCode, Cursor, etc.
├── GEMINI.md -> AGENTS.md   # Compatibility link
├── .cursorrules -> AGENTS.md
├── bin/                     # Standalone CLI tools (deployed to ~/.local/bin/)
│   ├── lbat
│   ├── lmode
│   ├── lhz
│   ├── legion-profile-osd
│   └── test-hotkey
├── systemd/                 # User service unit
│   └── legion-profile-osd.service
├── tmpfiles.d/              # Boot-time permission configurations
│   ├── lenovo_conservation.conf
│   ├── lenovo_platform_profile.conf
│   └── lenovo_hotkeys.conf
├── icons/                   # Custom circular SVG badges
│   ├── quiet.svg
│   ├── balanced.svg
│   ├── performance.svg
│   ├── extreme.svg
│   └── custom.svg
├── desktop/                 # KDE desktop entry for global shortcut binding
│   └── lhz-toggle.desktop
├── docs/                    # Reference guides & mount documentation
│   ├── Legion_Pro_7_16IAX10H_Hardware_Guide.md
│   ├── Legion_16IAX10H_Battery_Conservation_CachyOS.md
│   └── CachyOS_NTFS_Mount_Guide.md
└── install.sh               # 1-click installer and synchronizer
```

---

## 📜 Architectural Directives for AI Agents

For guidelines on coding style, hardware constraints, safety rules, and filesystem integrity, consult [.agents/AGENTS.md](.agents/AGENTS.md).
