#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 🚀 Deploying Lenovo Legion Linux Toolkit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Deploy CLI binaries
echo "📦 Installing CLI tools to ~/.local/bin/..."
mkdir -p "$HOME/.local/bin"
find "$DIR/bin" -maxdepth 1 -type f -exec cp -v {} "$HOME/.local/bin/" \;
chmod +x "$HOME"/.local/bin/{lbat,lmode,lhz,lcolor,lstats,lcopilot,legion-profile-osd,test-hotkey}

# 2. Deploy default configuration (only if not already present)
echo "⚙️  Ensuring ~/.config/legion/config.jsonc exists..."
mkdir -p "$HOME/.config/legion"
if [[ ! -f "$HOME/.config/legion/config.jsonc" && ! -f "$HOME/.config/legion/config.json" ]]; then
    if [[ -f "$DIR/config/config.example.jsonc" ]]; then
        cp -v "$DIR/config/config.example.jsonc" "$HOME/.config/legion/config.jsonc"
    fi
else
    echo "   Skipped: ~/.config/legion configuration already exists"
fi

# 3. Deploy SVG badges & Color Profiles
echo "🎨 Installing circular SVG badges to ~/.local/share/icons/legion/..."
mkdir -p "$HOME/.local/share/icons/legion"
cp -v "$DIR"/icons/*.svg "$HOME/.local/share/icons/legion/"

echo "🎨 Installing factory-calibrated color profiles to ~/.local/share/color/icc/..."
mkdir -p "$HOME/.local/share/color/icc"
if [[ -d "$DIR/color-profiles" ]]; then
    cp -v "$DIR"/color-profiles/*.icm "$HOME/.local/share/color/icc/" 2>/dev/null || true
fi

# 4. Deploy rofi theme (only if not already present — never override user's customization)
echo "🎨 Installing Legion Quick Launcher rofi theme..."
mkdir -p "$HOME/.config/rofi"
if [[ ! -f "$HOME/.config/rofi/legion-launcher.rasi" ]]; then
    cp -v "$DIR"/config/rofi/legion-launcher.rasi "$HOME/.config/rofi/"
else
    echo "   Skipped: ~/.config/rofi/legion-launcher.rasi already exists (user-customized)"
fi

# 5. Deploy desktop shortcuts & systemd user service
if [[ -d "$DIR/desktop" ]]; then
    echo "🖥️  Installing desktop shortcut entries to ~/.local/share/applications/..."
    mkdir -p "$HOME/.local/share/applications"
    cp -v "$DIR"/desktop/*.desktop "$HOME/.local/share/applications/" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

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
    # sysfs nodes: battery conservation, platform profile & MMIO RAPL limits
    sudo cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    for conf in "$DIR"/tmpfiles.d/*.conf; do
        sudo systemd-tmpfiles --create "/etc/tmpfiles.d/$(basename "$conf")"
    done

    # /dev/input/ devices & external DRM connector status nodes
    if [[ -d "$DIR/udev" ]]; then
        sudo cp -v "$DIR"/udev/*.rules /etc/udev/rules.d/
        sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=input && sudo udevadm trigger --subsystem-match=drm
    fi
else
    cp -v "$DIR"/tmpfiles.d/*.conf /etc/tmpfiles.d/
    for conf in "$DIR"/tmpfiles.d/*.conf; do
        systemd-tmpfiles --create "/etc/tmpfiles.d/$(basename "$conf")"
    done

    if [[ -d "$DIR/udev" ]]; then
        cp -v "$DIR"/udev/*.rules /etc/udev/rules.d/
        udevadm control --reload-rules && udevadm trigger --subsystem-match=input && udevadm trigger --subsystem-match=drm
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete! All Legion features are active:"
echo "   - lbat         : Battery Conservation (~80% cap / 100% full)"
echo "   - lmode        : Power & Thermal Profiles (Quiet, Balanced, Perf, Extreme)"
echo "   - lhz          : Display Refresh Rate (240Hz / 60Hz)"
echo "   - lcolor       : Display Color Profile Manager (sRGB, Display P3, DCI-P3...)"
echo "   - lstats       : Hardware & Platform Telemetry CLI (Live Dashboard)"
echo "   - lcopilot     : External keyboard trigger for Copilot Tap / Quick Launch"
echo "   - Fn + Q       : Hardware 3-mode power loop + OSD banner"
echo "   - Fn + R       : Hardware refresh rate toggle + OSD banner"
echo "   - Fn + L       : Display color profile cycle (EDID-validated) + OSD banner"
echo "   - Fn + N       : Configurable app toggle launcher (Default: nvtop)"
echo "   - Copilot Key  : Configurable hardware key (Default: Alacritty)"
echo "   - test-hotkey  : Hardware input event discovery sniffer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
