#!/usr/bin/env bash
# 鴨 Dakku: give Dakku a secure (https) address on your Tailscale network.
#
# Why: on iPhone, notifications ("your duck hatched") and opening Dakku with no connection both
# need https. Tailscale serves Dakku at https://<this-pc>.<your-tailnet>.ts.net with a real
# certificate, reachable only by your own devices. Nothing is opened to the internet.
#
# Run once, in Dakku's folder:   scripts/enable-https.sh
# Undo:       tailscale serve --https=443 off
set -euo pipefail

PORT="${DAKKU_PORT:-8640}"
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
json() { tailscale status --json | python3 -c "import json, sys; d = json.load(sys.stdin); $1"; }

command -v tailscale >/dev/null || { echo "Tailscale isn't installed."; exit 1; }
DNS=$(json 'print((d.get("Self") or {}).get("DNSName", "").rstrip("."))')
[ -n "$DNS" ] || { echo "Tailscale isn't connected. Run:  sudo tailscale up"; exit 1; }
curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null || { echo "Dakku isn't running on port $PORT. Start it:  systemctl --user start dakku"; exit 1; }

certs() { json 'print(" ".join(d.get("CertDomains") or []))'; }
if [ -z "$(certs)" ]; then
  say "Step 1 of 2: switch on HTTPS for your tailnet"
  echo "In the page that opens (https://login.tailscale.com/admin/dns), find “HTTPS Certificates”"
  echo "and click “Enable HTTPS”. It's free and only names your own devices."
  xdg-open "https://login.tailscale.com/admin/dns" >/dev/null 2>&1 || true
  read -r -p "Press Enter once it's on… " _
  for _ in $(seq 1 30); do [ -n "$(certs)" ] && break; sleep 2; done
  [ -n "$(certs)" ] || { echo "Tailscale still reports no HTTPS certificates. Wait a minute and run this again."; exit 1; }
fi

say "Step 2 of 2: serving Dakku at https://$DNS"
if ! out=$(tailscale serve --bg --https=443 "http://127.0.0.1:$PORT" 2>&1); then
  if printf '%s' "$out" | grep -qi "denied\|operator\|permission"; then
    echo "Tailscale needs your password once, so your user can manage this from now on:"
    sudo tailscale set --operator="$USER"
    tailscale serve --bg --https=443 "http://127.0.0.1:$PORT"
  else
    printf '%s\n' "$out"
    exit 1
  fi
fi

say "Checking (the first visit fetches a certificate, which can take a little while)…"
ok=""
for _ in $(seq 1 20); do
  if curl -fsS --max-time 30 "https://$DNS/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done
[ -n "$ok" ] || { echo "https://$DNS isn't answering yet. Give it a minute, then open it in a browser."; exit 1; }

# Safety: through the https address you must sign in like any phone. If Dakku ever thought those
# requests came from this PC itself, it would let them in without a passcode, so stop serving.
if curl -fsS "https://$DNS/api/whoami" | grep -q '"trusted":true'; then
  tailscale serve --https=443 off >/dev/null 2>&1 || true
  echo "Stopped: Dakku treated the https address as this PC, which it must not. Nothing is being served."
  exit 1
fi

say "Done. Dakku is at  https://$DNS"
cat <<EOF

On your iPhone (with the Tailscale app switched on):
  1. Open https://$DNS in Safari.
  2. Tap Share → Add to Home Screen.
  3. Open Dakku from your Home Screen and sign in (Dakku on this PC → Settings → Add a device).
  4. Settings → Notifications → Turn on.
EOF
