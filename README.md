# infra

Declarative state of my own machines: what runs, from which compose file, with which
config. Secrets are not here — every value that matters is a `${VARIABLE}` and lives
in a host-local `.env`.

The project26 hosts (`us200`, `fi200` — chatmail, chrysalis) are a separate story and
deliberately out of scope.

## Layout

```
hosts/<host>/
  compose/        docker compose files, exactly as deployed
  etc/            host configuration: knot, postfix, traefik, systemd units
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
| `root-auth-1` | `ghcr.io/kivraid/kivraid` | authentication |
| `matrix-homeserver-1` | `jevolk/tuwunel` | Matrix homeserver (Rust) |
| `matrix-heisenbridge-1` | `ghcr.io/anotherdoesnm/heisenbridge` | IRC ↔ Matrix bridge |
| `matrix-ap-bridge-1` | `ghcr.io/haven-organization/matrix-appservice-activitypub` | AP ↔ Matrix (MAAP) |
| `irc-parley-1` | `prologic/parley` | IRC network |

On the host, outside Docker: **postfix** (mail relay for `doesnmlab.xyz`, listens on
`212.192.223.99`), **saslauthd**, **bird** (BGP, keeps the white IP's routes and
refreshes the dn42 ROA table), **knot** (authoritative DNS for `doesnmlab.xyz`),
**dns-api** (`knotc` over HTTP), **mika.service** (ipip tunnel + policy routing).

`compose/historical/` holds an older synapse + inspircd setup that is not deployed —
kept only because the files explain what used to be there.

## Restoring vps

1. Debian 12, docker, the key from `.tools/keys/`.
2. Copy `hosts/vps/` over.
3. Fill `.env` (`.env.example` lists the keys).
4. `etc/` paths mirror the system (`etc/knot/knot.conf` → `/etc/knot/knot.conf`).
5. `systemctl daemon-reload`, then `docker compose up -d` in each compose directory.
6. `mika.service` must come up before postfix — the unit already declares it.

## Secrets

| variable | service |
|---|---|
| `PARLEY_OIDC_CLIENT_SECRET` | parley |
| `TUWUNEL_REGISTRATION_TOKEN`, `TUWUNEL_IDENTITY_PROVIDER__0__CLIENT_SECRET`, `TUWUNEL_EMERGENCY_PASSWORD` | tuwunel |
| `INSP_OPER_PASSWORD_HASH` | historical pc/pc2 |

Never in git either: `/etc/dnsapi/{token,oidc-secret,session.key}`, `/root/desec.env`,
`/root/certs/acme.json`, `/root/frp/token.txt`, `/root/.ssh/`.

## Drift

`scripts/collect.sh` re-reads the host into this tree (sanitising secrets). Run it
before committing, so the repo describes reality rather than memory.
