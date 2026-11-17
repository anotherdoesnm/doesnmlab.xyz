# bird (the VPS)

`bird.conf` includes the dn42 pieces; `mika.conf` is the tunnel-adjacent peer and
`peers/` holds per-neighbour files. None of it carries secrets — dn42 peering is
identity-by-key, not password.

`roa_dn42_v6.conf` is **generated** and deliberately not tracked: it is a 140 KB dump of
the dn42 ROA table, refreshed every 15 minutes by `usr/local/sbin/bird-roa-refresh.sh`.
Committing it would mean a diff of thousands of lines on every refresh and a stale table
in the repository.
