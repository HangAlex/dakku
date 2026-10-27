#!/usr/bin/env bash
# 鴨 Dakku: run Dakku as a user service, so it starts with the PC (even before you log in)
# and restarts itself if it ever stops.
#
# Run once:   ~/mori/scripts/install-service.sh
# Undo:       systemctl --user disable --now mori && rm ~/.config/systemd/user/mori.service
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"

# A copy started by hand would hold the port; stop it first.
if pgrep -u "$USER" -f '^python3 -m mori$' >/dev/null; then
  echo "Stopping the copy of Dakku that's running by hand…"
  pkill -u "$USER" -f '^python3 -m mori$' || true
  sleep 1
fi

mkdir -p "$UNIT_DIR"
cp "$ROOT/systemd/mori.service" "$UNIT_DIR/mori.service"
systemctl --user daemon-reload
systemctl --user enable --now mori.service

# Linger lets user services run while you're logged out (it's already on for you; this keeps it so).
if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "Letting Dakku run while you're logged out (asks for your password once):"
  sudo loginctl enable-linger "$USER"
fi

for _ in $(seq 1 20); do
  curl -fsS http://127.0.0.1:8640/api/health >/dev/null 2>&1 && break
  sleep 0.5
done
if curl -fsS http://127.0.0.1:8640/api/health >/dev/null 2>&1; then
  echo
  echo "鴨 Dakku is running and will start with the PC."
  echo "  This PC:        http://localhost:8640"
  DNS=$(tailscale status --json 2>/dev/null | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)
  [ -n "$DNS" ] && echo "  With Tailscale: http://$DNS:8640"
  echo "  Status:         systemctl --user status mori"
else
  echo "Dakku didn't come up. Its log:"
  journalctl --user -u mori -n 30 --no-pager
  exit 1
fi
