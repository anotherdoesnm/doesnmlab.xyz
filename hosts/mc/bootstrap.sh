#!/bin/sh
# Provision the Minecraft container (LXC 151): Java 8, the 1.7.10 jar, lazymc and units.
#
#   sh bootstrap.sh --dry-run
#   sh bootstrap.sh
#
# Idempotent: it skips whatever is already in place.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

JAR_SHA1=952438ac4e01b4d115c5fc38f891710c4941df29
JAR_URL=https://launcher.mojang.com/v1/objects/$JAR_SHA1/server.jar
LAZYMC_URL=https://github.com/timvisee/lazymc/releases/download/v0.2.11/lazymc-v0.2.11-linux-x64-static

run() { if [ "$dry" = 1 ]; then printf '[dry] %s\n' "$*"; else "$@"; fi; }
put() { run install -D -m "${3:-644}" "$1" "$2"; }
say() { printf '\n== %s\n' "$*"; }

say "packages"
run apt-get update -qq
run env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl ca-certificates tar

say "Java 8 (Adoptium)"
if [ ! -x /opt/java8/bin/java ] || [ "$dry" = 1 ]; then
    # -4: this container gets AAAA records it has no route for.
    run sh -c "curl -4 -sL -o /tmp/jre8.tar.gz https://api.adoptium.net/v3/binary/latest/8/ga/linux/x64/jre/hotspot/normal/eclipse &&
               mkdir -p /opt/java8 && tar -xzf /tmp/jre8.tar.gz -C /opt/java8 --strip-components=1 && rm /tmp/jre8.tar.gz"
fi

say "server jar (official, sha1 checked)"
if [ ! -f /srv/minecraft/server.jar ] && [ "$dry" = 0 ]; then
    run mkdir -p /srv/minecraft
    run sh -c "curl -4 -sL -o /srv/minecraft/server.jar $JAR_URL"
fi
if [ "$dry" = 0 ]; then
    actual=$(sha1sum /srv/minecraft/server.jar | cut -d' ' -f1)
    [ "$actual" = "$JAR_SHA1" ] || { echo "server.jar sha1 mismatch: $actual" >&2; exit 1; }
fi

say "lazymc"
put "$here/etc/lazymc.toml" /etc/lazymc.toml
if [ ! -x /usr/local/bin/lazymc ] || [ "$dry" = 1 ]; then
    run sh -c "curl -4 -sL -o /usr/local/bin/lazymc $LAZYMC_URL && chmod 755 /usr/local/bin/lazymc"
fi

say "config and units"
put "$here/srv/minecraft/server.properties" /srv/minecraft/server.properties
put "$here/etc/systemd/system/lazymc.service" /etc/systemd/system/lazymc.service

if ! id minecraft >/dev/null 2>&1; then
    run useradd -r -d /srv/minecraft -s /usr/sbin/nologin minecraft
fi
run chown -R minecraft:minecraft /srv/minecraft
run systemctl daemon-reload
run systemctl enable lazymc
run systemctl restart lazymc

say "done"
printf '%s\n' \
    "External access is not provisioned here:" \
    "  frpc on nexus: [[proxies]] minecraft -> 192.168.1.61:25565, remotePort 10050" \
    "  VPS: hosts/vps/compose/mc-proxy (socat publishes 25565 -> frps:10050)"
