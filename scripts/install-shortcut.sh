#!/usr/bin/env bash
# 鴨 Dakku: a Dakku app on your dock. It opens your real Dakku (http://localhost:8640) in its own
# Brave window, with the duck icon; right-click it for the Pond, your Stats, or the demo.
#
# Run once:   ~/mori/scripts/install-shortcut.sh
# Undo:       ~/mori/scripts/install-shortcut.sh remove
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
ICON="$HOME/.local/share/icons/hicolor/512x512/apps/mori.png"
DESKTOP="$APPS/mori.desktop"

favorites() { gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]"; }

if [ "${1:-}" = "remove" ]; then
  now=$(favorites)
  if printf '%s' "$now" | grep -q "'mori.desktop'"; then
    gsettings set org.gnome.shell favorite-apps "$(python3 -c "import ast, sys; print([a for a in ast.literal_eval(sys.argv[1].replace('@as ', '')) if a != 'mori.desktop'])" "$now")"
  fi
  rm -f "$DESKTOP" "$ICON"
  echo "Dakku is off your dock."
  exit 0
fi

command -v brave-browser >/dev/null || { echo "This opens Dakku in Brave, which isn't installed."; exit 1; }

# the app icon with rounded corners and a little room around it, like the other icons on the dock
mkdir -p "$(dirname "$ICON")" "$APPS"
python3 - "$ROOT/web/icons/icon-512.png" "$ICON" <<'EOF'
import sys
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]
size, inner, big = 512, 456, 4
art = Image.open(src).convert("RGBA").resize((inner, inner), Image.LANCZOS)
mask = Image.new("L", (inner * big, inner * big), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner * big - 1, inner * big - 1], radius=int(inner * 0.23 * big), fill=255)
art.putalpha(mask.resize((inner, inner), Image.LANCZOS))
icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
icon.alpha_composite(art, ((size - inner) // 2, (size - inner) // 2))
icon.save(out)
EOF

# The window's name has to match StartupWMClass, so the dock shows it as Dakku and not as Brave.
# Brave names an --app window after its address and profile (measured on this PC).
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Dakku
GenericName=Study timer
Comment=鴨 Dakku: a duck for every focus session
Exec=brave-browser --app=http://localhost:8640/
Icon=$ICON
Terminal=false
Categories=Education;
Keywords=study;focus;timer;pomodoro;ducks;mori;
StartupWMClass=brave-localhost__-Default
StartupNotify=true
Actions=pond;stats;demo;

[Desktop Action pond]
Name=Pond
Exec=brave-browser "--app=http://localhost:8640/#forest"

[Desktop Action stats]
Name=Stats
Exec=brave-browser "--app=http://localhost:8640/#stats"

[Desktop Action demo]
Name=Demo (made-up ducks)
Exec=brave-browser --app=http://localhost:8642/
EOF
command -v desktop-file-validate >/dev/null && desktop-file-validate "$DESKTOP"
update-desktop-database "$APPS" 2>/dev/null || true

# pin it to the dock, after the apps already there
now=$(favorites)
if ! printf '%s' "$now" | grep -q "'mori.desktop'"; then
  gsettings set org.gnome.shell favorite-apps "$(python3 -c "import ast, sys; print(ast.literal_eval(sys.argv[1].replace('@as ', '')) + ['mori.desktop'])" "$now")"
fi
echo "Dakku is on your dock. Right-click it for the Pond, your Stats, or the demo."
