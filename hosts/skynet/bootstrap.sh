#!/bin/sh
# Provision skynet (LXC 111) from this directory. Idempotent: run it as often as you
# like, it only adds what is missing.
#
#   sh bootstrap.sh --dry-run     # print what would change
#   sh bootstrap.sh               # as root on the container
#
# What this does NOT do: install the application payload. Docker stacks and binaries
# are separate — see README.md.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

run() { if [ "$dry" = 1 ]; then printf '[dry] %s\n' "$*"; else "$@"; fi; }
put() { run install -D -m "${3:-644}" "$1" "$2"; }
say() { printf '\n== %s\n' "$*"; }

say "packages"
run apt-get update -qq
run env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ca-certificates curl gnupg iproute2 nftables nginx zstd

say "sysctl: ip forwarding"
put "$here/etc/sysctl.d/10-ip-forward.conf" /etc/sysctl.d/10-ip-forward.conf
# `sysctl --system` fails inside an unprivileged container: it walks host-level keys
# (kernel.pid_max, fs.protected_*) that this container may not write, and `set -e`
# would stop the script there. Apply only the file that is ours.
run sysctl -p /etc/sysctl.d/10-ip-forward.conf

say "nftables: NAT for LAN clients on the tunnel"
put "$here/etc/nftables/lan-nat.nft" /etc/nftables.d/lan-nat.nft
put "$here/etc/systemd/system/lan-nat.service" /etc/systemd/system/lan-nat.service
run systemctl daemon-reload
run systemctl enable lan-nat.service
run systemctl restart lan-nat.service

say "nginx: the DSH vhost"
put "$here/etc/nginx/snippets/dsh_proxy.conf" /etc/nginx/snippets/dsh_proxy.conf
put "$here/etc/nginx/sites-enabled/skynet" /etc/nginx/sites-enabled/skynet
run nginx -t
run systemctl reload nginx

say "ssh: the sftp-only tv account"
if ! id tv >/dev/null 2>&1; then
    run useradd -m -d /srv/tv -s /bin/false tv
    run mkdir -p /srv/tv
    run chown tv:tv /srv/tv
    run chmod 750 /srv/tv
fi
if ! grep -q 'Match User tv' /etc/ssh/sshd_config; then
    run sh -c "cat '$here/etc/ssh/match-tv.conf' >> /etc/ssh/sshd_config"
fi
run mkdir -p /run/sshd
run sshd -t
# No reload: on Debian sshd runs under socket activation (ssh.socket), and
# `systemctl reload ssh` starts a second sshd that cannot bind :22 and fails the unit.
# Each connection starts a fresh sshd, which reads this config anyway.

say "systemd units"
put "$here/etc/systemd/system/dsh-web.service" /etc/systemd/system/dsh-web.service
put "$here/etc/systemd/system/sokobot.service" /etc/systemd/system/sokobot.service
put "$here/usr/local/bin/dsh-web-run.sh" /usr/local/bin/dsh-web-run.sh 755
run systemctl daemon-reload
# Enable, but do not start: dsh-web is the harness this script may be running inside.
run systemctl enable dsh-web

say "done"
printf '%s\n' \
    "Not provisioned here (application payload):" \
    "  /opt/sokobot/SokobotNET  — built from anotherdoesnm/SokobotNET; the VPS runs" \
    "                             the same bot as a container from GHCR instead." \
    "  /opt/sokobot/.env        — FLUXER_TOKEN, never in git." \
    "  /etc/ssl/postfix, /etc/sasldb2 — secrets, regenerated on the host."
