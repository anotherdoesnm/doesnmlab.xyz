# infra

Declarative state of my own machines: what runs, from which compose file, with which
config. Secrets are not here — every value that matters is a `${VARIABLE}` and lives
in a host-local `.env`.

The project26 hosts (`us200`, `fi200` — chatmail, chrysalis) are a separate story and
deliberately out of scope.

## Layout

Three layers, from the metal up:

- `hosts/pve/lxc/` — container definitions (cores, memory, disk, network, onboot),
  one `pct config` per container, plus scripts to dump and recreate them;
- `hosts/<host>/` — the host layer: `bootstrap.sh` and the files it installs
  (nginx, sshd, sysctl, nftables, systemd units);
- `hosts/<host>/compose/` — the application layer: compose files and their configs.


```
hosts/<host>/
  compose/        docker compose files, exactly as deployed
  etc/            host configuration: postfix, traefik, systemd units
  usr/local/      small operator scripts that live outside packages
  .env.example    every variable the compose files need; real values in .env
```

`vps` is `150.241.64.73`, plus the white IP `212.192.223.99` brought up by
`mika.service` (an ipip tunnel; postfix waits for it).

## What actually runs on vps (from `docker ps`, 2026-11-14)

| container | image | what |
|---|---|---|
| `root-traefik-1` | `traefik:v3.7` | TLS + routing for every domain, ACME via deSEC |
| `frps` | `snowdreamtech/frps` | reverse tunnel to the home network |
| `homepage` | `homepage-patched:22.23.4` | dashboard |
| `irc-parley-1` | `prologic/parley` | IRC network |

On the host, outside Docker: **postfix** (mail relay for `doesnmlab.xyz`, listens on
`212.192.223.99`), **saslauthd**, **bird** (BGP, keeps the white IP's routes and
refreshes the dn42 ROA table), **mika.service** (ipip tunnel + policy routing).

## DSH Web UI (skynet)

The harness is served by `dsh-web.service` → `/usr/local/bin/dsh-web-run.sh`, which
starts `/bin/dsh --profile web --host 127.0.0.1 --port 3080` behind nginx
(`sites-enabled/skynet`, port 8443) and writes the launch token into
`/etc/nginx/dsh_token.inc` so the vhost can redirect `/?token=…` without anyone
pasting it.

**`--trusted-host` must list every authority the UI is reached by.** It is not
authentication (that is the token) but a separate browser-trust fence on `/api`.
A missing authority returns 403 to every API call, after which the client cannot
obtain `remoteAccess` and the page dies with:

```
Failed to load plugins — web boot: 3 required entries did not activate
… pending (waiting for service: remoteAccess / uiSession / uiWorkspace …)
```

The launcher therefore trusts the hostname and the LAN IP forms:

```
--trusted-host skynet.doesnmlab.xyz --trusted-host 192.168.1.30
--trusted-host 192.168.1.30:8443 --trusted-host 192.168.1.30:3080
```

Checking it without a browser: `curl -sk -H 'Host: <authority>' https://127.0.0.1:8443/api/plugins`
returns 401 (fence passed, needs cookie) rather than 403.

Upgrading DSH (`npm i -g @deepseek-ai/dsh@<version>`) needs `systemctl restart dsh-web`
plus a hard reload in the browser, because client bundles are cached by revision.

## Mail

`mail/` is the relay container: Debian postfix + saslauthd on host networking (it
must listen on the white IP `212.192.223.99` and reach the home tunnel that sshd
forwards to `127.0.0.1:10025`). The configuration is **baked into the image**, not
mounted over `/etc/postfix`: a bind mount hides the image's `dynamicmaps.cf`, and
Debian registers `cdb` support through that file.

Volumes: `data/spool`, `data/lib`, `data/mail`, `data/log` (postfix logs to
`maillog_file`, there is no syslog in the container), plus `/etc/ssl/postfix` for TLS
and `/secrets/sasldb2` — the SASL database is copied in with the container's own
group id, because a bind mount keeps the host's and smtpd cannot read it.

Rollback while the host package is still installed: `docker compose down` in
`mail/`, then `systemctl start postfix saslauthd`.

## DNS

The domain is served by **deSEC** (anycast, DNSSEC, API); there is no self-hosted
authoritative DNS any more. Until 2026-11-20 `dns/` was a compose project of its own —
knot `cznic/knot:v3.6.2` plus `dns-api` (HTTP over `knotc`) — but the zone it served was
only a copy of the deSEC one, nothing delegated to it, and Traefik's `rfc2136` resolver
issued exactly zero certificates in its lifetime. Both containers and both config trees
were removed; this file's history has them if the delegation ever moves back.

The stale `_matrix._tcp` and `_matrix-fed._tcp` SRV records went with the homeserver.

Source checkouts under `/root` (for example the `heisenbridge` clones with their
own `docker-compose.yml` test harness) are **not** infra and are not in this repo —
what matters about them is the image tag that runs, not the checkout.

## Restoring vps

1. Debian 12, docker, the key from `.tools/keys/`.
2. Copy `hosts/vps/` over.
3. Fill `.env` (`.env.example` lists the keys).
4. `etc/` paths mirror the system (`etc/traefik/homenet.yml` → `/root/traefik/homenet.yml` as a volume).
5. `systemctl daemon-reload`, then `docker compose up -d` in each compose directory.
6. `mika.service` must come up before postfix — the unit already declares it.

## Secrets

| variable | service |
|---|---|
| `PARLEY_OIDC_CLIENT_SECRET` | parley |
| `TUWUNEL_REGISTRATION_TOKEN`, `TUWUNEL_IDENTITY_PROVIDER__0__CLIENT_SECRET`, `TUWUNEL_EMERGENCY_PASSWORD` | tuwunel |

Never in git either: `/etc/dnsapi/{token,oidc-secret,session.key}`, `/root/desec.env`,
`/root/certs/acme.json`, `/root/frp/token.txt`, `/root/.ssh/`.

## Drift

`scripts/collect.sh` re-reads the host into this tree (sanitising secrets). Run it
before committing, so the repo describes reality rather than memory.
