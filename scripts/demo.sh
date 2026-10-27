#!/usr/bin/env bash
# 鴨 Dakku demo: a second Dakku full of made-up ducks, for showing people what a full pond looks like.
# It keeps its own data (~/mori/demo/), never touches your real Dakku, and opens without signing in.
#
#   ~/mori/scripts/demo.sh             run it now, until you press Ctrl+C
#   ~/mori/scripts/demo.sh install     keep it running all the time (so your phone can always open it)
#   ~/mori/scripts/demo.sh uninstall   switch that off again
#   ~/mori/scripts/demo.sh reset       start over with fresh made-up ducks
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${MORI_DEMO_PORT:-8642}"
UNIT="$HOME/.config/systemd/user/mori-demo.service"

addresses() {
  echo "  This PC:    http://localhost:$PORT"
  DNS=$(tailscale status --json 2>/dev/null | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)
  [ -n "$DNS" ] && echo "  Your phone: http://$DNS:$PORT   (with Tailscale on)"
  return 0
}
by_hand() { pgrep -u "$USER" -f 'python3 -m mori --demo$' >/dev/null && ! systemctl --user is-active --quiet mori-demo.service; }

case "${1:-run}" in
  run)
    if systemctl --user is-active --quiet mori-demo.service; then
      echo "The demo is already running all the time:"; addresses; exit 0
    fi
    echo "鴨 Dakku demo, with made-up ducks (Ctrl+C stops it):"
    addresses
    cd "$ROOT"
    exec python3 -m mori --demo
    ;;
  install)
    if by_hand; then echo "Stop the demo you started by hand first (Ctrl+C in its window)."; exit 1; fi
    mkdir -p "$(dirname "$UNIT")"
    cp "$ROOT/systemd/mori-demo.service" "$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --now mori-demo.service
    for _ in $(seq 1 20); do
      curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
      sleep 0.5
    done
    if ! curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
      echo "The demo didn't come up. Its log:"
      journalctl --user -u mori-demo -n 30 --no-pager
      exit 1
    fi
    echo "The Dakku demo is running and will start with the PC:"
    addresses
    ;;
  uninstall)
    systemctl --user disable --now mori-demo.service 2>/dev/null || true
    rm -f "$UNIT"
    systemctl --user daemon-reload
    echo "The demo is off. Its made-up ducks are kept in $ROOT/demo (\"demo.sh reset\" clears them)."
    ;;
  reset)
    if by_hand; then echo "Stop the demo you started by hand first (Ctrl+C in its window)."; exit 1; fi
    active=""
    systemctl --user is-active --quiet mori-demo.service && active=1
    [ -n "$active" ] && systemctl --user stop mori-demo.service
    rm -rf "$ROOT/demo"
    [ -n "$active" ] && systemctl --user start mori-demo.service
    echo "Done: the demo starts over with fresh made-up ducks."
    ;;
  *)
    sed -n 2,8p "$0"
    exit 1
    ;;
esac
