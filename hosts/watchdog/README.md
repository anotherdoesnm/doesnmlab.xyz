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
## cheburprobe is off (2026-11-19)

The probe was running but could not do its job, and the reason is not the token:
`PROBE_ID=56` and `PROBE_TOKEN` sit in `/etc/default/cheburprobe` and reach the process —
MQTT connects fine. It fails on **DPI calibration**:

```
WARN DPI calibration for [2606:4700:4700::1111]:443 is unknown: method=post_client_hello, reason=connect_error
```

That target is IPv6, and the home network has none (`ip -6 addr` empty, `ping -6` →
"Network is unreachable"). With calibration unknown, tasks fail as `no config`, and the
hourly downtime adds a backlog that the probe can never drain: 907 tasks expired in ten
minutes while 8 failed, none completed.

The owner has already told Cheburcheck that this network has no IPv6; until they stop
assigning IPv6 calibration to probe 56, the service stays disabled. Re-enable with
`systemctl enable --now cheburprobe` once they do.
