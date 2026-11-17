#!/bin/sh
# Provision gate (LXC 130): the split-horizon resolver.
#
#   sh bootstrap.sh --dry-run
#   sh bootstrap.sh
#
# /etc/dnsmasq.conf itself is the stock Debian file and is not tracked: everything we
# change lives in /etc/dnsmasq.d/, which dnsmasq reads by default.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

run() { if [ "$dry" = 1 ]; then printf '[dry] %s\n' "$*"; else "$@"; fi; }
put() { run install -D -m "${3:-644}" "$1" "$2"; }
say() { printf '\n== %s\n' "$*"; }

say "packages"
run apt-get update -qq
run env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq dnsmasq nftables

say "dnsmasq: split horizon"
put "$here/etc/dnsmasq.d/local-split.conf" /etc/dnsmasq.d/local-split.conf
# The stock example file ships a README next to it; keep ours only if it is absent.
[ -f /etc/dnsmasq.d/README ] || put "$here/etc/dnsmasq.d/README" /etc/dnsmasq.d/README

# dnsmasq must listen on the LAN address, not the container's loopback only.
run systemctl enable dnsmasq
run systemctl restart dnsmasq

say "verify"
if [ "$dry" = 0 ]; then
    if command -v dig >/dev/null 2>&1; then
        dig +short +time=3 @127.0.0.1 doesnmlab.xyz || true
    else
        printf 'dig not installed; check from the LAN instead:\n  dig @192.168.1.40 doesnmlab.xyz\n'
    fi
fi

say "done"
printf '%s\n' \
    "Not provisioned here:" \
    "  /etc/dnsmasq.conf — stock Debian file, unmodified on this host." \
    "  /etc/nftables.conf — stock Debian file as well." \
    "  The upstream forwarders (192.168.1.254, 1.1.1.1) live in local-split.conf."
