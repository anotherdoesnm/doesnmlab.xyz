# SokobotNET (fluxer.com)

`docker compose up -d` here, with `.env` holding `FLUXER_TOKEN`. The image is built by
the bot's own repository and published to GHCR:

    ghcr.io/anotherdoesnm/sokobotnet:master

The local test copy of the same bot lives on skynet in `/opt/sokobot` as
`sokobot.service` and points at our instance instead, with
`FLUXER_INSTANCE=https://fluxer.doesnmlab.xyz/api`.
