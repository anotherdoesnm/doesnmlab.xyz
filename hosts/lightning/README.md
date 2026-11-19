# lightning — мост IRC ↔ Fluxer

Замена связки `tuwunel + heisenbridge`. У lightning есть нативные плагины IRC и Fluxer
(Fluxer обслуживается discord-плагином: `api_host` содержит `fluxer` → API v1), поэтому
Matrix из схемы выпадает целиком.

## Почему VPS, а не LXC

Гостевые контейнеры живут на pve, а хост выключается ночью по `nightly-poweroff.timer` —
мост ложился бы вместе с ним. VPS работает круглосуточно, а сам бот занимает ~40–60 МБ
RSS (Go + SQLite), что для 612 МБ свободных приемлемо. Юнит ограничен `MemoryMax=192M`,
чтобы бот не стал причиной уже почти исчерпанного swap.

## Патч `hide_author`

При отсутствии IRCv3 `draft/relaymsg` lightning клеит префикс `[ник]: текст`. Патч
добавляет опцию `hide_author`, и сообщения уходят голым текстом — в канале видно
`<lightning> текст` вместо `<lightning> [ник]: текст`.

Ограничение честное: **без relaymsg подделать источник сообщения нельзя**, протокол
всегда несёт отправителя. Relaymsg умеет Ergo (и h4ks по словам владельца), parley и
retronode — нет. На стороне Fluxer незаметность достигается вебхуками, там ограничений нет.

## Сборка

```sh
# на VPS
cd /root/lightning-src
docker run --rm -v "$PWD":/src -w /src golang:1.26 go build -o /src/lightning ./cmd/lightning
```

Исходники — архив `develop` с codeberg.org/jersey/lightning (symlink README.md → docs/index.md
делает `curl .../raw/branch/develop/README.md` бесполезным: он отдаёт 13 байт).

## Мост в базе

```sql
INSERT INTO bridges (id, codes, allow_everyone, add_platform_name)
VALUES ('<uuid>', '[]', false, false);

INSERT INTO bridge_channels (bridge_id, channel_id, data) VALUES
  ('<uuid>', '<id канала Fluxer>', '{"plugin":"fluxer"}'),
  ('<uuid>', '#канал',            '{"plugin":"parley"}');
```
