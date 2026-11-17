# mc (LXC 151) — Minecraft 1.7.10, on demand

A 1.7.10 server for a few friends, with `lazymc` in front: the proxy answers status while
the server sleeps and starts the JVM on the first join, stopping it after five idle
minutes.

| | |
|---|---|
| container | 151, `192.168.1.61`, 2 vCPU, 2 GiB, 10 GB, `onboot: 0` |
| java | Adoptium JRE 8 in `/opt/java8` (Debian 12 has no openjdk-8, and 1.7.10 wants 8) |
| server | `/srv/minecraft/server.jar`, the official jar `952438ac…` from Mojang |
| proxy | `lazymc` on `0.0.0.0:25565` → `127.0.0.1:25566` |
| external | `150.241.64.73:25565` — frpc proxy `minecraft` (remotePort 10050) + `mc-proxy` sidecar on the VPS |

`server.properties` and `etc/lazymc.toml` are tracked; the world is not (it is data, and it
lives in `/srv/minecraft/world`).

## Why lazymc

The host shuts down at 22:00 MSK, and nobody plays around the clock. lazymc keeps the JVM
off until somebody actually connects: an idle container uses ~15 MB, a running server
~220 MB. It does not talk to the Proxmox API — it starts and stops the local `java`
process, which is the right layer: the container itself costs almost nothing.

## Provisioning

```sh
sh bootstrap.sh          # java 8, the jar (checked by sha1), lazymc, units
pct set 151 --onboot 1   # so the proxy survives a host reboot
```

`bootstrap.sh` downloads the jar itself and checks it against `952438ac…`, so the
repository never carries a 9.4 MB blob. Inside this container every fetch needs `curl -4`:
DNS returns AAAA records the container has no route for, and the download dies on them
while `curl -I` happily succeeds.

## Notes

- Protocol 5 is 1.7.10; 47 is 1.8. A status ping with the wrong protocol still answers.
- `online-mode=true`: the server checks Mojang sessions, so pirated clients cannot join.
- The audit of the public port: `mc-proxy` on the VPS is a socat container in
  `traefik_network`, because Traefik only routes HTTP(S) and frps publishes no ports.
