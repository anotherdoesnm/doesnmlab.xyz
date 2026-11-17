# fluxer-test (LXC 150) — the Fluxer instance

A self-hosted Discord-alike on 1 GiB. `compose/` holds the upstream compose file
exactly as deployed plus our overlays; `.env.example` lists every key the stack reads.

```sh
cd /srv/fluxer
docker compose -f docker-compose.yml -f docker-compose.external-db.yml \
               -f docker-compose.proxy.yml -f docker-compose.no-search.yml up -d
```

| overlay | why it exists |
|---|---|
| `external-db` | Postgres and S3 live on nexus (`192.168.1.10`), not in this container — the shipped stack does not fit in 1 GiB |
| `no-search` | Meilisearch is off: the API builds a provider, throws during startup and exits, so the supported no-search shape is the Elasticsearch branch with blank credentials |
| `proxy` | edge behind the LAN/nginx entry point |
| `lan-ports` / `search-shim` | local experiments, documented so they are not rediscovered |

Two things that bite when this is rebuilt:

- Compose **produces** `FLUXER_POSTGRES_PASSWORD`, `FLUXER_S3_ACCESS_KEY_ID` and
  `FLUXER_S3_SECRET_ACCESS_KEY` from `POSTGRES_PASSWORD`, `FLUXER_S3_ACCESS_KEY` and
  `FLUXER_S3_SECRET_KEY` in `.env`. Setting the `FLUXER_*` names directly does nothing.
- `onboot: 0`: the instance sleeps with the host most of the time, and the nightly e2e
  in `fluxer-worker-lite` no longer pretends otherwise.
