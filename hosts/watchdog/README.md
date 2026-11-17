# watchdog (LXC 120) — reachability sampling and third-party probes

Three services, only one of them ours:

| unit | what | payload |
|---|---|---|
| `netwatch.service` | samples ICMP / TCP443 / TLS-SNI to homelab endpoints into `/var/log/netwatch.csv`, to catch DPI block windows | `usr/local/bin/netwatch.py`, in this repository |
| `cheburprobe.service` | Cheburcheck dynamic probe | binary from its own package, unit in `/lib/systemd/system` |
| `globalping-probe.service` | Globalping probe | `/opt/globalping-probe`, node |

`bootstrap.sh` provisions the first one and leaves the other two documented but
unshipped — installing somebody else's probe from a copy of a binary is worse than
running their installer.

The CSV is the point: four columns per sample (`icmp`, `tcp443`, `tls_sni`,
`tls_nosni`) separate "route is gone" from "packets are filtered" from "only SNI
filtering", which one boolean could never tell apart.
