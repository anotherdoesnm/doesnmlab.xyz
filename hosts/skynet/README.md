# skynet (LXC 111) — host layer

`bootstrap.sh` brings a fresh container up to the state this one is in: packages,
sysctl, the LAN NAT unit, the nginx vhost that fronts the harness, the sftp-only `tv`
account and the systemd units. It is idempotent — re-run it after any manual change
and the repository wins.

```sh
sh bootstrap.sh --dry-run     # print what would change
sh bootstrap.sh               # as root, on the container
```

It is run through the Proxmox host, which is the only path into the containers:

```sh
ssh pve 'pct exec 111 -- sh -c "cd /path/to/hosts/skynet && sh bootstrap.sh"'
```

## What lives here

| file | on the host |
|---|---|
| `etc/nginx/sites-enabled/skynet` | the vhost on :8443 that injects the launch token |
| `etc/nginx/snippets/dsh_proxy.conf` | the proxy to `127.0.0.1:3080` |
| `etc/ssh/match-tv.conf` | appended `Match User tv` block, SFTP only |
| `etc/sysctl.d/10-ip-forward.conf` | `net.ipv4.ip_forward=1` |
| `etc/nftables/lan-nat.nft` + `etc/systemd/system/lan-nat.service` | masquerade for LAN clients on `awg0` |
| `etc/systemd/system/dsh-web.service`, `usr/local/bin/dsh-web-run.sh` | the harness and its launcher |
| `etc/systemd/system/sokobot.service` | the local test copy of the bot |

## What it deliberately does not do

- **The bot binary.** `/opt/sokobot/SokobotNET` is built from
  `anotherdoesnm/SokobotNET`; the VPS runs the same bot as a container from GHCR.
- **Secrets.** `/opt/sokobot/.env` (`FLUXER_TOKEN`), `/etc/ssl/postfix/*`, `/etc/sasldb2`.
- **Application payload.** Anything Docker, plus the YunoHost-managed parts of nexus.

## Three traps this script already knows about

1. **`sysctl --system` fails in an unprivileged container** — it walks host-level keys
   (`kernel.pid_max`, `fs.protected_*`) that the container may not write, and `set -e`
   stops the script. Only the project's own file is applied.
2. **`systemctl reload ssh` breaks the unit.** Debian runs sshd under socket activation;
   reload starts a second sshd that cannot bind :22. The config is re-read on every
   connection, so the script validates with `sshd -t` and stops there.
3. **`/etc/nftables.conf` starts with `flush ruleset`.** Adding an include there and
   reloading would wipe the wg-quick tables the tunnel needs, so the NAT rule lives in
   its own oneshot unit that runs after `awg-quick@awg0.service`.
