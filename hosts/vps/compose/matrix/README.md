# Matrix — decommissioned 2026-11-20

`matrix.doesnmlab.xyz`: tuwunel 2.0.0 with a RocksDB database, federation on, plus
heisenbridge as the Matrix↔IRC appservice (`heisen.…`). Both containers and images are
gone; this directory is the record of how the stack ran, not a deployable unit.

## Where the data went

`matrix-dump-2026-11-20.tar.zst` — 857 MiB, sha256
`cdc61e26910a27ad84a9b51efbf373d3fda3e5c7ac129881a4b36430413ff08b` — now lives at
`93.123.13.148:/home/doesnm/db/`, verified there with `sha256sum -c`. It holds `db/`
(RocksDB plus `media/`), a README, the admin-API manifest of the 923 rooms that existed
before the purge, `purge-plan.json`, and redacted copies of these two files.

Before packing, 863 rooms without `@doesnm` and 2360 media files were purged through the
Synapse-compatible admin API: 923 → 60 rooms, 5477 → 2436 media files, 3.3 → 1.2 GiB.
The 60 kept are 18 rooms with `@doesnm` and 42 with `@mika`/`@dsalin`/`@zulip`.

## Deliberately not in git

The real `TUWUNEL_REGISTRATION_TOKEN`, `TUWUNEL_IDENTITY_PROVIDER__0__CLIENT_SECRET`,
`TUWUNEL_EMERGENCY_PASSWORD`, and heisenbridge `as_token`/`hs_token` are redacted here.
They lived in `/root/matrix/compose.yml` and `/root/matrix/heisenbridge.yaml` on the VPS,
together with the `db/` directory, which is now the only remaining copy and can be
deleted once a re-transfer is clearly not needed.

## Traps that cost time

- `scp` to that host fails with `Connection closed` — its sshd has no SFTP subsystem.
  Use `scp -O`. It also rejected `ssh-ed25519` until `PubkeyAcceptedAlgorithms` was
  widened, so the RSA-4096 key stays as a fallback.
- Media lives in `db/media/` because the compose mounts only `./db`; the online backup
  commands (`!admin server backup-database`) do **not** include it.
- The admin API (`/_synapse/admin/...`) works: log in as `@conduit` with the emergency
  password and keep the access token — it survives restarts until logout.
- heisenbridge keeps no database of its own: per-user network config is Matrix
  `account_data`, so it was inside the dump all along.
