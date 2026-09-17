#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 🚀 Deploying Lenovo Legion Linux Toolkit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Deploy CLI binaries
echo "📦 Installing CLI tools to ~/.local/bin/..."
mkdir -p "$HOME/.local/bin"
cp -v "$DIR"/bin/* "$HOME/.local/bin/"
chmod +x "$HOME"/.local/bin/{lbat,lmode,lhz,legion-profile-osd,test-hotkey}

# 2. Deploy default configuration (only if not already present)
echo "⚙️  Ensuring ~/.config/legion/config.json exists..."
mkdir -p "$HOME/.config/legion"
if [[ ! -f "$HOME/.config/legion/config.json" ]]; then
    cat > "$HOME/.config/legion/config.json" << 'JSONEOF'
{
  "copilot_tap": "/usr/bin/alacritty",
  "copilot_candidates": [
    { "key": "1", "name": "Alacritty Terminal",         "exec": "/usr/bin/alacritty" },
    { "key": "2", "name": "Konsole Terminal",            "exec": "konsole" },
    { "key": "3", "name": "KRunner Spotlight Search",    "exec": "krunner" },
    { "key": "4", "name": "Screenshot (Spectacle)",      "exec": "spectacle -r" },
    { "key": "5", "name": "Antigravity IDE",             "exec": "antigravity" }
  ],
  "fn_n_command": "alacritty -e nvtop"
}
JSONEOF
fi

# 3. Deploy SVG badges
echo "🎨 Installing circular SVG badges to ~/.local/share/icons/legion/..."
mkdir -p "$HOME/.local/share/icons/legion"
cp -v "$DIR"/icons/*.svg "$HOME/.local/share/icons/legion/"

# 4. Deploy rofi theme (only if not already present — never override user's customization)
echo "🎨 Installing Legion Quick Launcher rofi theme..."
mkdir -p "$HOME/.config/rofi"
if [[ ! -f "$HOME/.config/rofi/legion-launcher.rasi" ]]; then
    cp -v "$DIR"/config/rofi/legion-launcher.rasi "$HOME/.config/rofi/"
else
    echo "   Skipped: ~/.config/rofi/legion-launcher.rasi already exists (user-customized)"
fi
echo "🖥️  Installing desktop shortcut for KDE Plasma..."
mkdir -p "$HOME/.local/share/applications"
cp -v "$DIR"/desktop/*.desktop "$HOME/.local/share/applications/"
kbuildsycoca6 2>/dev/null || true

# 5. Deploy systemd user service
echo "⚙️  Deploying legion-profile-osd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp -v "$DIR"/systemd/*.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now legion-profile-osd.service

# 6. Deploy hardware permissions (requires sudo)
# Architecture:
#   /etc/tmpfiles.d/ → ONLY for static /sys/ sysfs nodes (lbat, lmode)
#   /etc/udev/rules.d/ → ALL /dev/input/ devices (tmpfiles 'z' does NOT follow symlinks)
echo "🔒 Configuring hardware permissions (/etc/tmpfiles.d/ and /etc/udev/rules.d/)..."
if [[ $EUID -ne 0 ]]; then
    # sysfs nodes: battery conservation & platform profile
    sudo cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_conservation.conf
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_platform_profile.conf

    # /dev/input/ devices: ITE Keyboard (Copilot) + Ideapad Hotkeys (Fn+R, Fn+L)
    if [[ -d "$DIR/udev" ]]; then
        sudo cp -v "$DIR"/udev/*.rules /etc/udev/rules.d/
        sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=input
    fi
else
    cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_conservation.conf
    systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_platform_profile.conf

    if [[ -d "$DIR/udev" ]]; then
        cp -v "$DIR"/udev/*.rules /etc/udev/rules.d/
        udevadm control --reload-rules && udevadm trigger --subsystem-match=input
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete! All Legion features are active:"
echo "   - lbat         : Battery Conservation (~80% cap / 100% full)"
echo "   - lmode        : Power & Thermal Profiles (Quiet, Balanced, Perf, Extreme)"
echo "   - lhz          : Display Refresh Rate (240Hz / 60Hz)"
echo "   - Fn + Q       : Hardware 3-mode power loop + OSD banner"
echo "   - Fn + R       : Hardware refresh rate toggle + OSD banner"
echo "   - Fn + L       : Hardware Legion Logo toggle + 3D OSD badge"
echo "   - Copilot Key  : Configurable hardware key (Default: Alacritty)"
echo "   - test-hotkey  : Hardware input event discovery sniffer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
