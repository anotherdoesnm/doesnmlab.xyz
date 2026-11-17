# LXC definitions

One file per container, exactly as `pct config <id>` prints it. This is the source of
truth for cores, memory, swap, features, network, root size and `onboot` — everything
that used to live only in `docs/topology.md`.

| id | hostname | address | memory | disk | onboot |
|---|---|---|---|---|---|
| 110 | nexus | 192.168.1.10 | 4 GiB | 28 G | 1 |
| 111 | skynet | 192.168.1.30 | 4 GiB | 12 G | 1 |
| 120 | watchdog | 192.168.1.20 | 3 GiB | 6 G | 1 |
| 130 | gate | 192.168.1.40 | 192 MiB | 1 G | 1 |
| 150 | fluxer-test | 192.168.1.60 | 1 GiB | 8 G | 0 |

Two details worth not rediscovering:

- **All five are unprivileged.** `111 skynet` additionally gets `/dev/net/tun` through
  `dev0` — an unprivileged container cannot create the tun node itself, and the
  AmneziaWG tunnel needs it.
- **`150 fluxer-test` sits at .60**, not the .109 written in older notes.

The MAC addresses are part of the definition on purpose: the LAN reserves addresses
for them, so a rebuilt container keeps its IP.

## Rebuilding

```sh
# from a backup — the normal path, keeps data
pct restore 130 /var/lib/vz/dump/vzdump-lxc-130-*.tar.zst --storage local-lvm

# from scratch — empty root filesystem, then replay the container's own IaC
sh scripts/lxc-recreate.sh hosts/pve/lxc/130-gate.conf local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst --run
```

A fresh container has the right shape and nothing inside it: the services come from
`hosts/<host>/` (compose files, nginx vhosts, systemd units) and from the per-service
documents in `docs/`.

## After changing a container by hand

```sh
sh scripts/lxc-dump.sh     # on the node, rewrites these files
```
