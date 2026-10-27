#!/usr/bin/env bash
# 鴨 Dakku: study with friends, with nothing for them to install or set up.
#
# Your own Dakku stays private on your Tailscale network. This opens a second, separate door just
# for the friends you invite, at https://<this-pc>.<your-tailnet>.ts.net:8443, through Tailscale
# Funnel (free, part of Tailscale). Anyone can reach that address, but only someone with an invite
# or a sign-in link from you gets in, and then only to their own pond, your groups' ponds and the
# sessions they can join: never your settings, your data, your devices or your passcode, none of
# which work there.
#
# Run once:   ~/mori/scripts/enable-friends.sh
# Undo:       ~/mori/scripts/enable-friends.sh off    (friends can't reach Dakku until you run it again)
set -euo pipefail

FRIENDS_PORT="${MORI_FRIENDS_PORT:-8643}"
HTTPS_PORT=8443  # Funnel offers 443 (your own Dakku's), 8443 and 10000
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
json() { tailscale status --json | python3 -c "import json, sys; d = json.load(sys.stdin); $1"; }
close_door() { tailscale funnel --https=$HTTPS_PORT off >/dev/null 2>&1 || tailscale serve --https=$HTTPS_PORT off >/dev/null 2>&1 || true; }

command -v tailscale >/dev/null || { echo "Tailscale isn't installed."; exit 1; }

if [ "${1:-}" = "off" ]; then
  close_door
  echo "The friends' door is closed: only your own devices can reach Dakku. Your friends' ponds are kept."
  exit 0
fi

DNS=$(json 'print((d.get("Self") or {}).get("DNSName", "").rstrip("."))')
[ -n "$DNS" ] || { echo "Tailscale isn't connected. Run:  sudo tailscale up"; exit 1; }
[ -n "$(json 'print(" ".join(d.get("CertDomains") or []))')" ] || { echo "Run ~/mori/scripts/enable-https.sh first: friends use the same secure address."; exit 1; }
if ! curl -fsS "http://127.0.0.1:$FRIENDS_PORT/api/health" >/dev/null 2>&1; then
  echo "Dakku's door for friends (port $FRIENDS_PORT) isn't open. Restart Dakku so it runs the latest version:"
  echo "  systemctl --user restart mori"
  exit 1
fi

say "Opening the friends' door at https://$DNS:$HTTPS_PORT"
echo "If Tailscale asks you to switch Funnel on, a page opens: click Enable, and this carries on by itself."
log=$(mktemp)
watcher=""
trap 'rm -f "$log"; [ -n "$watcher" ] && kill "$watcher" 2>/dev/null; true' EXIT
# open Tailscale's "enable Funnel" page in the browser as soon as it's offered
( for _ in $(seq 1 1200); do
    url=$(grep -o 'https://login\.tailscale\.com/[^[:space:]]*' "$log" 2>/dev/null | head -n 1 || true)
    if [ -n "$url" ]; then xdg-open "$url" >/dev/null 2>&1 || true; exit 0; fi
    sleep 0.5
  done ) &
watcher=$!
funnel() { tailscale funnel --bg --https=$HTTPS_PORT "http://127.0.0.1:$FRIENDS_PORT" 2>&1 | tee "$log"; }
if ! funnel; then
  if grep -qi "denied\|operator\|permission" "$log"; then
    echo "Tailscale needs your password once, so your user can manage this from now on:"
    sudo tailscale set --operator="$USER"
    funnel
  else
    exit 1
  fi
fi

say "Checking…"
ok=""
for _ in $(seq 1 20); do
  if curl -fsS --max-time 30 "https://$DNS:$HTTPS_PORT/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done
[ -n "$ok" ] || { echo "https://$DNS:$HTTPS_PORT isn't answering yet. Give it a minute, then run this again."; exit 1; }

# Safety: that address has to be the friends' door, where nobody is this PC and none of your own
# pages are. If it isn't, close it again at once.
who=$(curl -fsS "https://$DNS:$HTTPS_PORT/api/whoami" || true)
if ! printf '%s' "$who" | grep -q '"public":true' || printf '%s' "$who" | grep -q '"trusted":true'; then
  close_door
  echo "Stopped: that address didn't reach Dakku's door for friends, so it's closed again. Nothing is open to the internet."
  exit 1
fi

say "Done. Friends can now reach Dakku at  https://$DNS:$HTTPS_PORT"
cat <<EOF

To bring someone in:
  1. In Dakku, open 共 Together and make a group (say, "Us").
  2. Tap Invite, and send them the link (or let them scan the QR code).
  3. They open it, pick a name, a color and a little badge, and they're in: no app, no account, no Tailscale.
     On iPhone they can then Share → Add to Home Screen, and sign in there with the 6-digit code from
     Dakku in Safari (Settings → Add a device).

The first time, Funnel can take a few minutes to reach the whole internet. To try it yourself, open an
invite link on your phone with Wi-Fi and Tailscale switched off.
Who's in, and removing anyone: Dakku → Settings → People & groups.
Closing the door again:  ~/mori/scripts/enable-friends.sh off
EOF
