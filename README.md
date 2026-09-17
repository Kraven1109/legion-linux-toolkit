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
| **`lcolor`** | Display Color Profile Manager | `status`, `cycle` (Fn+L), `set <name>`, `list` |
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
├── AGENTS.md                # Universal AI developer entrypoint
├── bin/                     # Standalone CLI tools (deployed to ~/.local/bin/)
│   ├── lbat
│   ├── lcolor
│   ├── lhz
│   ├── lmode
│   ├── legion-profile-osd
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

## 📜 Architectural Directives for AI Agents

For guidelines on coding style, hardware constraints, safety rules, and filesystem integrity, consult [.agents/AGENTS.md](.agents/AGENTS.md).
