#!/usr/bin/env python3
"""Sample reachability of the homelab endpoints that DPI keeps knocking out.

One CSV row per destination per interval, appended to /var/log/netwatch.csv:

    ts,label,ip,icmp,tcp443,tls_sni,tls_nosni

Why four columns and not one: they separate the failure modes.

  icmp=0                 the route itself is gone (null-route, dead link)
  icmp=1 tcp443=0        the filter drops packets to that IP at the network layer
  icmp=1 tcp443=1 tls_sni=0 tls_nosni=1
                         the SYN gets through, the TLS ClientHello does not: a
                         DPI rule keyed on the destination IP and applied to
                         identifiable TLS, which is exactly the "dynamic block"
                         that comes and goes
  everything 1           normal service
  tcp443=0 with icmp=1 and a refused connection
                         host is up, nothing listens on 443 (not a block)

The controls (github, cloudflare, ya.ru) exist so a block window can be told
apart from a broken line: if the controls fail too, the problem is local.

Journal events (`journalctl -u netwatch`):

  WAVE-START label ip      first blocked sample of a window
  WAVE-END   label ip dur=Ns  service came back, window length
  ROUND      n=42 blocked=a,b heartbeat, every ROUND_LOG rounds
  CORRELATE  ...           third-party vantage, at most one per window and no
                           sooner than CORRELATE_GAP
  ALERT white-ip-down/up   the clean-range address stopped (or resumed) answering
  ALERT long-block         a single destination has been blocked longer than
                           LONG_WAVE, so it is an outage and not a wave

Window state lives in this process, so a restart drops an open window: a
WAVE-START without a matching WAVE-END means the sampler restarted mid-window.
"""

import concurrent.futures as cf
import csv
import json
import os
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

INTERVAL = int(os.environ.get("NETWATCH_INTERVAL", "120"))
ROUND_LOG = int(os.environ.get("NETWATCH_ROUND_LOG", "15"))
CORRELATE_GAP = int(os.environ.get("NETWATCH_CORRELATE_GAP", "300"))
SKIP_FILE = os.environ.get("NETWATCH_SKIP_FILE", "/etc/netwatch-skip")
OUT = os.environ.get("NETWATCH_OUT", "/var/log/netwatch.csv")
PORT_OUT = os.environ.get("NETWATCH_PORTS_OUT", "/var/log/netwatch-ports.csv")
ALERT_LOG = os.environ.get("NETWATCH_ALERT_LOG", "/var/log/netwatch-alerts.log")
# A block that outlives this is no longer a "wave" but an outage worth a nudge.
LONG_WAVE = int(os.environ.get("NETWATCH_LONG_WAVE", "1800"))
# The one address we care about keeping reachable no matter what is being blocked.
WHITE_IP = os.environ.get("NETWATCH_WHITE_IP", "vps-212")
# Consecutive failed rounds before a white-IP alert fires (ICMP alone can be
# rate-limited, so one lost packet is not news).
WHITE_IP_STRIKES = int(os.environ.get("NETWATCH_WHITE_IP_STRIKES", "2"))

TARGETS = [
    ("doesnmlab", "150.241.64.73", "doesnmlab.xyz"),
    ("cm-dc09", "146.19.128.227", "cm.dc09.xyz"),
    ("git-p26", "45.94.47.109", "git.project26.cc"),
    ("project26", "45.158.196.56", "project26.cc"),
    ("de-cm3", "185.122.171.85", "cm3.project26.cc"),
    # canaries: neighbouring addresses we do not own. If a wave hits the
    # neighbour too, the filter works on the subnet; if only our address falls,
    # the list is per IP.
    # Probed every 15th round instead of every round: the A/B for "does our own
    # probing keep the prefix hot". It shares 45.94.47.0/24 with git-p26, so a
    # prefix-wide filter hits both identically; a difference in duty cycle between
    # the 2-minute and the 30-minute target is the observer showing up in the data.
    ("canary-45.94.47.100", "45.94.47.100", "canary.example.com", 15),
    # The "white IP": a /32 announced over BGP and tunnelled to the VPS. It is a
    # domestic destination from this line, so it is the candidate replacement for
    # everything that currently shares a blocked prefix. 443 has no listener yet,
    # so a tcp443=0 row here means "nothing is served", not "filtered".
    ("vps-212", "212.192.223.99", "matrix.doesnmlab.xyz"),
    # controls
    ("github", "140.82.121.3", "github.com"),
    ("cloudflare", "104.16.0.1", "cloudflare.com"),
    ("yandex", "77.88.44.55", "ya.ru"),
]

# Mail and SSH run on their own ports to the same hosts, so the 443 probe cannot
# tell whether the filter keys on the port or only on TLS. Measured separately:
#
#   ports.csv: ts,label,ip,port,tcp,tls_sni,banner
# The last field is how to decide the service answered: `tls` finishes a
# handshake, `ssh` waits for an "SSH-" greeting, `http` asks for a page. A plain
# TCP connect says nothing: during the mild block the SYN is answered and the
# data is dropped. Port 80 is the discriminator the operator named — when plain
# HTTP still works the block is the mild 443-only kind, when HTTP dies too it is
# the carpet kind.
PORT_TARGETS = [
    ("cm-dc09-imap", "146.19.128.227", 993, "cm-dc09", "tls"),
    ("cm-dc09-submission", "146.19.128.227", 465, "cm-dc09", "tls"),
    ("git-p26-ssh", "45.94.47.109", 22, "git-p26", "ssh"),
    ("de-cm3-ssh", "185.122.171.85", 22, "de-cm3", "ssh"),
    ("doesnmlab-ssh", "150.241.64.73", 22, "doesnmlab", "ssh"),
    ("doesnmlab-http", "150.241.64.73", 80, "doesnmlab", "http"),
    ("vps-212-ssh", "212.192.223.99", 22, "vps-212", "ssh"),
    ("vps-212-https", "212.192.223.99", 443, "vps-212", "tls"),
    ("cm-dc09-http", "146.19.128.227", 80, "cm-dc09", "http"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def icmp(ip: str) -> int:
    return int(subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)


def tcp(ip: str, port: int = 443, timeout: float = 2.5) -> int:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return 1
    except OSError:
        return 0
    finally:
        s.close()


def tls(ip: str, sni, timeout: float = 4.0) -> int:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, 443))
        ss = ctx.wrap_socket(s, server_hostname=sni) if sni else ctx.wrap_socket(s)
        ss.close()
        return 1
    except Exception:
        return 0
    finally:
        try:
            s.close()
        except OSError:
            pass


def ssh_greeting(ip: str, port: int = 22, timeout: float = 5.0) -> int:
    """The SSH server speaks first; a dropped greeting is as good as a wall."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return 1 if s.recv(255).startswith(b"SSH-") else 0
    except OSError:
        return 0
    finally:
        s.close()


def http_page(ip: str, port: int = 80, timeout: float = 4.0) -> int:
    """Plain HTTP, no TLS: it answers the "mild or carpet" question."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.sendall(b"GET / HTTP/1.0\r\nHost: netwatch\r\nConnection: close\r\n\r\n")
        return 1 if s.recv(64) else 0
    except OSError:
        return 0
    finally:
        s.close()


def port_probe(ip: str, port: int, mode: str) -> tuple:
    """Returns (tcp, tls_ok, service_ok); the third column is mode-specific."""
    ok_tcp = tcp(ip, port)
    ok_tls = 0
    ok_svc = 0
    if ok_tcp:
        if mode == "tls":
            s = socket.socket()
            s.settimeout(4)
            try:
                s.connect((ip, port))
                ss = ctx.wrap_socket(s, server_hostname="mail.example.com")
                ss.close()
                ok_tls = 1
            except Exception:
                ok_tls = 0
            finally:
                try:
                    s.close()
                except OSError:
                    pass
        elif mode == "ssh":
            ok_svc = ssh_greeting(ip, port)
        elif mode == "http":
            ok_svc = http_page(ip, port)
    return ok_tcp, ok_tls, ok_svc


# --- third-party vantage ---------------------------------------------------
#
# The signature alone cannot tell "they block that destination for everyone in
# RU" from "they block this one line". check-host.net answers it: it runs an
# HTTP request from nodes in many countries, including three in Russia, and
# reports each node's result. One verdict per block window, never per sample:
# check-host rate-limits, and a throttled control check looks exactly like a
# real outage.

CHECKHOST = "https://check-host.net"
RU_NODES = ["ru1.node.check-host.net", "ru2.node.check-host.net", "ru3.node.check-host.net"]
EU_NODES = ["de1.node.check-host.net", "nl1.node.check-host.net"]


def _get(url: str, timeout: float = 15.0):
    # check-host answers 403 to the default python-urllib user agent.
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "netwatch/1.0 (homelab reachability diagnostics)",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def check_host(url: str, nodes) -> tuple:
    """Returns (ok, total) for an HTTP check from the given check-host nodes."""
    query = urllib.parse.urlencode({"host": url})
    req_url = f"{CHECKHOST}/check-http?{query}&" + "&".join("node=" + n for n in nodes)
    try:
        start = _get(req_url)
        rid = start.get("request_id")
        if not rid:
            return (0, len(nodes))
    except Exception as exc:
        print(f"netwatch: check-host start failed: {exc}", flush=True)
        return (0, len(nodes))
    for _ in range(6):
        time.sleep(3)
        try:
            res = _get(f"{CHECKHOST}/check-result/{rid}")
        except Exception:
            continue
        if any(v is None for v in res.values()):
            continue
        ok = 0
        for node in nodes:
            entry = res.get(node)
            if not entry:
                continue
            first = entry[0] if isinstance(entry, list) else entry
            # check-host returns [1, time, status, code, ip] on success,
            # {"error": ...} or a string on failure.
            if isinstance(first, list) and first and first[0] == 1:
                ok += 1
        return (ok, len(nodes))
    return (0, len(nodes))


last_correlate = 0.0


def correlate(label: str, domain: str) -> None:
    global last_correlate
    now = time.time()
    if now - last_correlate < CORRELATE_GAP:
        print(f"CORRELATE {label} skipped (rate limit, {int(CORRELATE_GAP - (now - last_correlate))}s left)",
              flush=True)
        return
    last_correlate = now
    ru_ok, ru_n = check_host(f"https://{domain}/", RU_NODES)
    eu_ok, eu_n = check_host(f"https://{domain}/", EU_NODES)
    ctl_ru_ok, ctl_ru_n = check_host("https://github.com/", RU_NODES)
    if ctl_ru_ok < 2:
        # The control fails from RU probes too, so the probes cannot tell us
        # anything about this destination.
        verdict = "probes-unavailable"
        # Back off: hammering a throttled probe service invents outages.
        last_correlate = time.time() + 3 * CORRELATE_GAP
    elif ru_ok >= 2:
        # Other people in Russia reach it while this line does not.
        verdict = "our-line-only"
    elif ru_ok == 0 and eu_ok >= 1:
        # Nobody in Russia reaches it; outside Russia it is fine.
        verdict = "destination-blocked-in-RU"
    else:
        verdict = "unclear"
    print(f"CORRELATE {label} {domain} local=blocked RU={ru_ok}/{ru_n} EU={eu_ok}/{eu_n} "
          f"RU-control-github={ctl_ru_ok}/{ctl_ru_n} verdict={verdict}", flush=True)


def deep_probe(label: str, ip: str, sni: str) -> None:
    """What exactly the filter keys on, asked once per window.

    The same IP is tried with: our own name (known blocked), a fresh subdomain
    under our name (tells a suffix rule from an exact-name rule) and an
    unrelated name (tells a name rule from a whole-IP rule). The no-SNI
    handshake in the round already proves the server itself answers.
    """
    stamp = time.strftime("%H%M%S")
    names = [f"zq{stamp}.{sni}", "example.com"]
    for name in names:
        res = "ok" if tls(ip, name) else "dropped"
        print(f"DEEP {label} {ip} sni={name} {res}", flush=True)


def probe_target(ip: str, sni: str) -> tuple:
    """One row of the matrix: (icmp, tcp443, tls_with_sni, tls_without_sni)."""
    tcp_ok = tcp(ip)
    return (icmp(ip), tcp_ok, tls(ip, sni) if tcp_ok else 0, tls(ip, None) if tcp_ok else 0)


def read_skip() -> set:
    try:
        with open(SKIP_FILE) as sfh:
            return {line.strip() for line in sfh if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


def needs_header(path: str) -> bool:
    return not os.path.exists(path) or os.path.getsize(path) == 0


def alert(kind: str, text: str) -> None:
    """Fire a notification: journal, a dedicated log, and an optional webhook.

    The alert about this line going dark cannot travel over this line, so the
    default channel is local (journal + /var/log/netwatch-alerts.log). Point
    NETWATCH_HOOK at anything that accepts a JSON POST — an ntfy topic, a
    Matrix/Telegram bridge, the bots' HTTP API — and it gets delivered there
    too. Delivery failure never breaks sampling.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"{ts} ALERT {kind} {text}"
    print(line, flush=True)
    try:
        with open(ALERT_LOG, "a") as afh:
            afh.write(line + "\n")
    except OSError as exc:
        print(f"netwatch: alert log unwritable: {exc}", flush=True)
    hook = os.environ.get("NETWATCH_HOOK", "").strip()
    if not hook:
        return
    try:
        body = json.dumps({"kind": kind, "text": text, "ts": ts}).encode()
        req = urllib.request.Request(hook, data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "netwatch/1.0 (homelab reachability diagnostics)",
        })
        urllib.request.urlopen(req, timeout=5).close()
    except Exception as exc:
        print(f"netwatch: alert hook failed: {exc}", flush=True)


def sample_round(out_fh, ports_fh, state: dict, round_no: int) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    skip = read_skip()
    out_w = csv.writer(out_fh)
    ports_w = csv.writer(ports_fh)

    # Probe in parallel: sequentially, every blocked target costs a full TLS
    # timeout, and a six-target wave stretched the round to almost four minutes —
    # which is exactly when the resolution is needed.
    # Targets may carry a period: probe them every Nth round only.
    todo = []
    for entry in TARGETS:
        label, ip, sni = entry[0], entry[1], entry[2]
        period = entry[3] if len(entry) > 3 else 1
        if label in skip or round_no % period != 0:
            continue
        todo.append((label, ip, sni))
    with cf.ThreadPoolExecutor(max_workers=max(4, len(todo))) as pool:
        futures = {pool.submit(probe_target, ip, sni): (label, ip) for label, ip, sni in todo}
        results = [(futures[f][0], futures[f][1], f.result()) for f in cf.as_completed(futures)]

    for label, ip, (icmp_ok, tcp_ok, sni_ok, nosni_ok) in sorted(results):
        row = [ts, label, ip, icmp_ok, tcp_ok, sni_ok, nosni_ok]
        out_w.writerow(row)
        signature = tcp_ok == 1 and sni_ok == 0 and nosni_ok == 1
        st = state.setdefault(label, {"blocked": False, "since": 0.0, "down": 0, "down_alert": False,
                                      "long_alert": False})

        # White-IP watchdog: if this address ever joins the blocked set, the whole
        # "move the services to a clean range" plan stops working, and we want to
        # hear it from the sampler rather than from a user complaint.
        if label == WHITE_IP:
            if icmp_ok:
                if st["down_alert"]:
                    st["down_alert"] = False
                    alert("white-ip-up", f"{label} {ip} answering again after {st['down']} round(s)")
                st["down"] = 0
            else:
                st["down"] += 1
                if st["down"] >= WHITE_IP_STRIKES and not st["down_alert"]:
                    st["down_alert"] = True
                    alert("white-ip-down", f"{label} {ip} unreachable for {st['down']} round(s)")

        if signature and not st["blocked"]:
            st["blocked"] = True
            st["since"] = time.time()
            st["long_alert"] = False
            print(f"{ts} WAVE-START {label} {ip} (tcp ok, tls+sni dropped, tls no-sni ok)", flush=True)
            correlate(label, sni)
            deep_probe(label, ip, sni)
        elif not signature and st["blocked"]:
            dur = int(time.time() - st["since"])
            st["blocked"] = False
            st["since"] = 0.0
            print(f"{ts} WAVE-END {label} {ip} dur={dur}s", flush=True)
        elif signature and st["blocked"] and not st["long_alert"]:
            dur = int(time.time() - st["since"])
            if dur >= LONG_WAVE:
                st["long_alert"] = True
                alert("long-block", f"{label} {ip} blocked for {dur}s (longer than {LONG_WAVE}s)")

    out_fh.flush()

    ports_todo = [(label, ip, port, mode) for label, ip, port, skip_label, mode in PORT_TARGETS if skip_label not in skip]
    with cf.ThreadPoolExecutor(max_workers=max(4, len(ports_todo))) as pool:
        port_futures = {pool.submit(port_probe, ip, port, mode): (label, ip, port) for label, ip, port, mode in ports_todo}
        port_results = [(port_futures[f][0], port_futures[f][1], port_futures[f][2], f.result())
                        for f in cf.as_completed(port_futures)]
    for label, ip, port, (t, ttls, tbanner) in sorted(port_results):
        ports_w.writerow([ts, label, ip, port, t, ttls, tbanner])
    ports_fh.flush()

    if round_no % ROUND_LOG == 0:
        open_waves = sorted(l for l, s in state.items() if s["blocked"])
        print(f"ROUND n={round_no} blocked={','.join(open_waves) or '-'}", flush=True)


def main() -> int:
    stop = {"now": False}

    def _stop(_signum, _frame):
        stop["now"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    out_fh = open(OUT, "a", newline="")
    ports_fh = open(PORT_OUT, "a", newline="")
    state = {}
    try:
        if needs_header(OUT):
            csv.writer(out_fh).writerow(["ts", "label", "ip", "icmp", "tcp443", "tls_sni", "tls_nosni"])
            out_fh.flush()
        if needs_header(PORT_OUT):
            csv.writer(ports_fh).writerow(["ts", "label", "ip", "port", "tcp", "tls_sni", "banner"])
            ports_fh.flush()

        round_no = 0
        next_tick = time.time()
        while not stop["now"]:
            round_no += 1
            sample_round(out_fh, ports_fh, state, round_no)
            # Fixed cadence: time spent inside a round is subtracted, not added.
            next_tick += INTERVAL
            now = time.time()
            if next_tick < now:
                next_tick = now
            while not stop["now"] and time.time() < next_tick:
                time.sleep(min(1.0, next_tick - time.time()))
    finally:
        for fh in (out_fh, ports_fh):
            try:
                fh.flush()
                fh.close()
            except Exception:
                pass
        open_waves = sorted(l for l, s in state.items() if s["blocked"])
        if open_waves:
            print(f"STOP open waves: {','.join(open_waves)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
