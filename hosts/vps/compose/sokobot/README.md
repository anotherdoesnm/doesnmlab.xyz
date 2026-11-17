# SokobotNET (fluxer.com)

`docker compose up -d` here, with `.env` holding `FLUXER_TOKEN`. The image is built by
the bot's own repository and published to GHCR:

    ghcr.io/anotherdoesnm/sokobotnet:master

The local test copy of the same bot lives on skynet in `/opt/sokobot` as
`sokobot.service` and points at our instance instead, with
`FLUXER_INSTANCE=https://fluxer.doesnmlab.xyz/api`.

## The data directory

```sh
mkdir -p /root/sokobot/data && chown 1000:1000 /root/sokobot/data && chmod 700 /root/sokobot/data
```

The image runs as uid 1000 and mounts the directory at `/data`, where SQLite keeps the
per-guild prefixes. Root ownership of a 0700 directory is enough to make the bot fail on
startup with `unable to open database file`.

The local test copy on skynet keeps its own database in `/var/lib/sokobot/` (a systemd
`StateDirectory`), separate from this one.
