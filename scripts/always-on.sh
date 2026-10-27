#!/usr/bin/env bash
# 鴨 Dakku: keep this PC on around the clock, with the screens going dark by themselves.
#
# Dakku lives on this PC, so while it's suspended your phone can't reach Dakku and the demo is gone.
# This switches suspend off for good (the Suspend button, the power button, and the login screen's
# own auto-suspend after a restart), turns the screens off after a few idle minutes instead, and
# adds a "Screens off" app that darkens them right away. Any key or mouse move wakes them.
#
# Run once:   ~/mori/scripts/always-on.sh        (asks for your password once)
# Undo:       ~/mori/scripts/always-on.sh undo
set -euo pipefail

BLANK_MINUTES="${BLANK_MINUTES:-5}"
TARGETS=(sleep.target suspend.target hibernate.target hybrid-sleep.target)
APPS="$HOME/.local/share/applications"
LAUNCHER="$APPS/screens-off.desktop"
ICON="$HOME/.local/share/icons/hicolor/512x512/apps/screens-off.png"
# GNOME's own screen blank, the one after 5 idle minutes. (Switching the displays off directly left
# them off for good: GNOME never knew to switch them back on.) It waits a second, so the click or the
# keys that started it don't count as waking up.
BLANK='sh -c "sleep 1; gdbus call --session --dest org.gnome.ScreenSaver --object-path /org/gnome/ScreenSaver --method org.gnome.ScreenSaver.SetActive true"'
HOTKEY='<Control><Super>End'  # the key marked Page Down on this PC's GMMK Pro sends End
KEYS=org.gnome.settings-daemon.plugins.media-keys
KEY_PATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/mori-screens-off/
shortcuts() { gsettings get $KEYS custom-keybindings; }

if [ "${1:-}" = "undo" ]; then
  echo "Letting the PC suspend again (asks for your password):"
  sudo systemctl unmask "${TARGETS[@]}"
  rm -f "$LAUNCHER" "$ICON"
  gsettings set $KEYS custom-keybindings "$(python3 -c "import ast, sys; print([k for k in ast.literal_eval(sys.argv[1].replace('@as ', '')) if k != sys.argv[2]])" "$(shortcuts)" "$KEY_PATH")"
  for key in name command binding; do gsettings reset "$KEYS.custom-keybinding:$KEY_PATH" $key; done
  echo "Suspend is back. The screens still turn off when idle: change that in Settings → Power → Screen Blank."
  exit 0
fi

# the screens go dark after a few idle minutes; the PC itself never sleeps on its own
gsettings set org.gnome.desktop.session idle-delay $((BLANK_MINUTES * 60))
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'

# and it can't be suspended at all, from anywhere
echo "Switching suspend off for the whole PC (asks for your password once):"
sudo systemctl mask "${TARGETS[@]}"

# "Screens off", as an app and as Ctrl+Super+Page Down (End to the computer): the screens go dark right away, and any key
# or mouse move wakes them.
mkdir -p "$APPS" "$(dirname "$ICON")"
python3 - "$ICON" <<'EOF'
import sys
from PIL import Image, ImageDraw
S = 4 * 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
pad, r = int(S * 0.055), int(S * 0.2)
d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=r, fill=(15, 23, 39, 255),       # Dakku's night blue,
                    outline=(52, 70, 108, 255), width=int(S * 0.012))                           # with a rim for the dark dock
d.ellipse([S * 0.27, S * 0.24, S * 0.73, S * 0.70], fill=(244, 236, 214, 255))            # the moon...
d.ellipse([S * 0.40, S * 0.17, S * 0.86, S * 0.63], fill=(15, 23, 39, 255))               # ...made a crescent
for x, y, s in ((0.70, 0.30, 0.022), (0.78, 0.48, 0.016), (0.60, 0.72, 0.014), (0.30, 0.78, 0.018)):
    d.ellipse([S * (x - s), S * (y - s), S * (x + s), S * (y + s)], fill=(87, 199, 207, 255))  # teal stars
img.resize((512, 512), Image.LANCZOS).save(sys.argv[1])
EOF
cat > "$LAUNCHER" <<EOF
[Desktop Entry]
Type=Application
Name=Screens off
Comment=Turn the monitors off now. Any key or mouse move wakes them; the PC and Dakku keep running.
Exec=$BLANK
Icon=$ICON
Terminal=false
Categories=Utility;
Keywords=monitor;screen;display;off;blank;dark;sleep;
EOF
command -v desktop-file-validate >/dev/null && desktop-file-validate "$LAUNCHER"
update-desktop-database "$APPS" 2>/dev/null || true
gsettings set "$KEYS.custom-keybinding:$KEY_PATH" name "'Screens off'"
gsettings set "$KEYS.custom-keybinding:$KEY_PATH" command "'$BLANK'"
gsettings set "$KEYS.custom-keybinding:$KEY_PATH" binding "'$HOTKEY'"
if ! shortcuts | grep -q "$KEY_PATH"; then
  gsettings set $KEYS custom-keybindings "$(python3 -c "import ast, sys; print(ast.literal_eval(sys.argv[1].replace('@as ', '')) + [sys.argv[2]])" "$(shortcuts)" "$KEY_PATH")"
fi

echo
echo "Done:"
echo "  • The screens turn off after $BLANK_MINUTES idle minutes. Any key or mouse move wakes them."
echo "  • The PC never suspends now, so Dakku is always reachable."
echo "  • Ctrl+Super+Page Down (your keyboard's, which sends End), or \"Screens off\" in your apps, darkens them right away."
