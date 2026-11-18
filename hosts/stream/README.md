# stream — Sunshine на виртуальном дисплее (CT152)

Гостевой контейнер для проверки игрового стриминга через Moonlight. Sunshine захватывает
`Xvfb :0` и кодирует **процессором** (x264), карта в этом режиме не участвует.

## Что уже проверено (2026-11-18)

| | |
|---|---|
| хост | `192.168.1.62`, Debian 13 (trixie), 8 ядер, 3 GiB |
| клиент | Oukitel WP23 Pro, Moonlight |
| рабочий режим | 1280x720 **30 fps**, 10 Мбит/с |
| network latency | 3 мс (variance 1) |
| host processing | 7.6 / 24.0 / 14.5 мс (min/max/avg) |
| decode на телефоне | 40 мс |
| dropped frames | 0 % |
| питание хоста | 69 Вт против 66 в простое |

**60 fps телефон не тянет:** decode подскакивает до ~99 мс, Moonlight пишет
«slow connection», хотя сеть тут ни при чём. Это ограничение клиента, не хоста.

## Создание контейнера (на хосте PVE)

```sh
pct create 152 local:vztmpl/debian-13-standard_13.6-1_amd64.tar.zst \
  --hostname stream --arch amd64 --ostype debian \
  --cores 8 --memory 3072 --swap 0 \
  --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,gw=192.168.1.254,ip=192.168.1.62/24 \
  --nameserver "192.168.1.40 1.1.1.1" \
  --unprivileged 0 --onboot 0 \
  --dev0 /dev/dri/card0 --dev1 /dev/dri/renderD128 --dev2 /dev/uinput
```

Затем в `/etc/pve/lxc/152.conf` — две строки, без которых ввода не будет:

```
lxc.mount.entry: /dev/input dev/input none bind,optional,create=dir 0 0
lxc.cgroup2.devices.allow: c 13:* rwm
```

## Грабли, собранные по одной

1. **Контейнер должен быть привилегированным.** В непривилегированном `/dev/dri` принадлежит
   `root:video`, а uid 0 внутри отображается на 100000 — доступа нет.
2. **`/dev/input` не появляется сам.** `pct set --dev3 /dev/input` не работает («is not a device»),
   нужна строка `lxc.mount.entry` выше. Без неё Sunshine создаёт устройство через `uinput`,
   но записать его в `/dev/input` некуда.
3. **cgroup запрещает чтение input.** Даже с примонтированным каталогом `evtest` и `jstest`
   получают `Operation not permitted`, пока не добавлен `c 13:* rwm`. Симптом: кнопки
   не доходят до игры вообще.
4. **Sunshine выходит без системного трея.** В логе `Failed to create system tray` →
   `Main loop has exited`. Лечится `system_tray = disabled`.
5. **CSRF.** Панель открывается по `https://192.168.1.62:47990`, а CSRF ждёт `localhost`:
   при вводе PIN — красный баннер. Нужен `csrf_allowed_origins`.
6. **Пакет только под trixie.** На bookworm установка падает на `libc6 >= 2.38` и t64-именах.
7. **Порядок запуска важен.** Геймпад (`js1`) создаётся в момент подключения клиента, поэтому
   игру надо запускать (или перезапускать) уже во время сессии — иначе она его не увидит.
8. **Мышь идёт через XTest, геймпад — через uinput.** Это разные пути: курсор может работать,
   когда кнопок нет, и наоборот.
9. **Звука нет:** в контейнере нет pulseaudio, в логе `Unable to initialize audio capture`.
10. **Оси стика приходят как триггеры.** В `jstest` двигаются `Z`/`Rz` (−32767), а `X`/`Y` стоят
    в нуле, поэтому в SuperTuxKart руль не появляется без переназначения управления.

## Чего здесь не сделать

WoT и подобное требуют Vulkan. На nouveau (legacy-ветка 470 не собирается на ядре 7.0)
Vulkan для Maxwell экспериментальный, так что рендерить игры через DXVK не на чем.
Этот контейнер — про «доезжает ли картинка», а не про игры.
