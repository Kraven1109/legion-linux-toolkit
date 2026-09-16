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

# 2. Deploy SVG badges
echo "🎨 Installing circular SVG badges to ~/.local/share/icons/legion/..."
mkdir -p "$HOME/.local/share/icons/legion"
cp -v "$DIR"/icons/*.svg "$HOME/.local/share/icons/legion/"

# 3. Deploy desktop shortcut
echo "🖥️  Installing desktop shortcut for KDE Plasma..."
mkdir -p "$HOME/.local/share/applications"
cp -v "$DIR"/desktop/*.desktop "$HOME/.local/share/applications/"
kbuildsycoca6 2>/dev/null || true

# 4. Deploy systemd user service
echo "⚙️  Deploying legion-profile-osd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp -v "$DIR"/systemd/*.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now legion-profile-osd.service

# 5. Deploy tmpfiles.d configurations (requires sudo)
echo "🔒 Configuring boot-time permissions in /etc/tmpfiles.d/..."
if [[ $EUID -ne 0 ]]; then
    sudo cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_conservation.conf
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_platform_profile.conf
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_hotkeys.conf
else
    cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_conservation.conf
    systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_platform_profile.conf
    systemd-tmpfiles --create /etc/tmpfiles.d/lenovo_hotkeys.conf
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete! All Legion features are active:"
echo "   - lbat         : Battery Conservation (~80% cap / 100% full)"
echo "   - lmode        : Power & Thermal Profiles (Quiet, Balanced, Perf, Extreme)"
echo "   - lhz          : Display Refresh Rate (240Hz / 60Hz)"
echo "   - Fn + Q       : Hardware 3-mode power loop + OSD banner"
echo "   - Fn + R       : Hardware refresh rate toggle + OSD banner"
echo "   - test-hotkey  : Hardware input event discovery sniffer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
