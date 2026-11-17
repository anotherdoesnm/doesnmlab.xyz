# gate (LXC 130) — split-horizon DNS

The LAN resolver. `doesnmlab.xyz` and its subdomains answer `192.168.1.10` (nexus, where
YunoHost serves the apps), everything else is forwarded upstream.

`bootstrap.sh` installs dnsmasq, drops `local-split.conf` into `/etc/dnsmasq.d/` and
restarts the service. The two files that stay untouched — `/etc/dnsmasq.conf` and
`/etc/nftables.conf` — are stock Debian and are deliberately not tracked.

```sh
sh bootstrap.sh --dry-run
sh bootstrap.sh
```
