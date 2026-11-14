# infra

Declarative state of the project's machines: what runs where, from which compose
file, with which config. Secrets are **not** here — every value that matters is a
`${VARIABLE}` and lives in a host-local `.env`.

## Layout

```
hosts/<host>/
  compose/        docker compose files, exactly as deployed
  etc/            host configuration: knot, postfix, traefik, systemd units
  usr/local/      small operator scripts that live outside packages
  .env.example    every variable the compose files need; real values in .env
```

`vps` is 150.241.64.73 (+ the white IP 212.192.223.99 from `mika.service`).

## What runs where (2026-11-14)

| host | containers | host services |
|---|---|---|
| `vps` | traefik, homepage, auth, frps, matrix (tuwunel + bridges), parley (irc), synapse + inspircd (pc, pc2) | postfix relay, saslauthd, bird (BGP + white IP), knot (DNS), dns-api, mika.service |
| `us200` | chatmail (13), chrysalis (6), mumble, mqtt, portainer, girafiles, searxng + valkey | amnezia (awg/xray) |
| `fi200` | chatmail (13), chrysalis (6), dnstt, postgres | amnezia (awg/xray) |

## Restoring a host

1. Base: Debian 12 + docker + the keys from `.tools/keys/`.
2. Copy `hosts/<host>/` to the machine.
3. Fill `.env` from the password manager (`.env.example` lists the keys).
4. `etc/` files go to their paths (paths are mirrored: `etc/knot/knot.conf` →
   `/etc/knot/knot.conf`); `systemctl daemon-reload` after units.
5. `docker compose up -d` in each compose directory.

## Secrets

| variable | where |
|---|---|
| `PARLEY_OIDC_CLIENT_SECRET` | vps, parley |
| `TUWUNEL_REGISTRATION_TOKEN`, `TUWUNEL_IDENTITY_PROVIDER__0__CLIENT_SECRET`, `TUWUNEL_EMERGENCY_PASSWORD` | vps, matrix |
| `INSP_OPER_PASSWORD_HASH` | vps, pc/pc2 |
| `MUMBLE_*_PASSWORD` | us200 |
| `POSTGRES_PASSWORD` | fi200 |

Also host-local and never in git: `/etc/dnsapi/{token,oidc-secret,session.key}`,
`/root/desec.env`, `/root/certs/acme.json`, `/root/frp/token.txt`,
`/root/searxng/.env`, `/root/.ssh/`.

## Drift

`scripts/collect.sh` re-reads the machines into this tree (sanitising secrets) —
run it before committing, so the repository describes reality rather than memory.
