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

## netwatch is off (2026-11-18)

The sampler wrote ~100k rows before it was stopped, and the CSV is kept gzipped in
`/var/log/netwatch.csv.gz`. It was switched off because the data stopped meaning what
the columns claim: `project26` (45.158.196.56) answers TCP and TLS but not ICMP, so the
first column reads like an outage on a healthy host, and the file had 100k rows of that.

`bootstrap.sh` still installs the unit but leaves it disabled — the script and the unit
stay in the repository for the next time a DPI question comes up.

## cheburprobe stays (2026-11-18)

A Telegram post argued against Cheburcheck: sites "died" days after being checked, the
site is not banned while its analogues are, and it is hosted in Russia (188.120.251.237).

Checked rather than repeated: the service is open source (Rust/Rocket, BSD-3) and the
`probe` agent we run is a measurement node, not a scanner of the sites themselves; the
"died after a check" claim is correlation — its audience checks what is already in the
registry. The real unknown is not the code but who queries what, which lives server-side.

We keep the probe: it costs this container nothing, nothing depends on it, and the only
exposure is that the homelab IP appears as a measurement point. If that ever stops being
acceptable, `systemctl disable --now cheburprobe` is the whole removal.

## cheburprobe works; the scary lines are noise (2026-11-19)

The probe is enabled and publishes results: **107 in five minutes**. Two things in the log
look like failures and are not.

`DPI calibration ... :443 is unknown: method=post_client_hello, reason=connect_error` — the
calibration target is IPv6 (`2606:4700:4700::1111`) and this network has no IPv6. The
project says to ignore it when the network lacks IPv6, and the probe keeps working.

`dropping expired queued task` — the host is off overnight, so the server queues tasks that
are stale by the time it boots; the probe discards them in bulk. 100 expiries against 107
published results in the same five minutes is normal, not a failure.

`failed to handle task ...: no config` — happens for a subset of task types (20 per five
minutes). It does not stop the rest.

Lesson recorded because it cost a wrong conclusion: count `probe/results/v1` publishes before
believing the warnings.

```sh
journalctl -u cheburprobe --since "-5 min" -o cat | grep -c probe/results/v1
```
