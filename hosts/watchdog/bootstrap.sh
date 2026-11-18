#!/bin/sh
# Provision watchdog (LXC 120): the reachability sampler we wrote, plus the two
# third-party probes whose payload is documented but not shipped here.
#
#   sh bootstrap.sh --dry-run
#   sh bootstrap.sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

run() { if [ "$dry" = 1 ]; then printf '[dry] %s\n' "$*"; else "$@"; fi; }
put() { run install -D -m "${3:-644}" "$1" "$2"; }

say() { printf '\n== %s\n' "$*"; }

say "packages"
run apt-get update -qq
run env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 nftables

say "netwatch: the DPI sampler"
put "$here/usr/local/bin/netwatch.py" /usr/local/bin/netwatch.py 755
put "$here/etc/systemd/system/netwatch.service" /etc/systemd/system/netwatch.service
run systemctl daemon-reload
# Installed but deliberately NOT enabled: as of 2026-11-18 the sampler is off.
# US-200 sits behind an ICMP static ban, so half the rows read "route gone" for a
# healthy host, and the CSV taught us to ignore its own alerts.
run systemctl disable --now netwatch 2>/dev/null || true

say "done"
printf '%s\n' \
    "Third-party payload, installed by their own means and deliberately not tracked:" \
    "  cheburprobe        — /usr/bin/cheburprobe, unit from /lib/systemd/system" \
    "  globalping-probe   — /opt/globalping-probe (node dist/index.js)" \
    "Their units are kept in etc/systemd/system/ so the shape is visible." \
    "" \
    "nftables here keeps the stock Debian file; no local ruleset is applied."
