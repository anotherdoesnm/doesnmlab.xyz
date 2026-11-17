#!/bin/sh
# Turn a dumped LXC config into a `pct create` command, so a container definition can
# be rebuilt on a fresh node without hand-reading YAML-less Proxmox config files.
#
#   sh lxc-recreate.sh hosts/pve/lxc/130-gate.conf local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst
#   sh lxc-recreate.sh ... --run        # actually create it
#
# The root filesystem is created empty at the recorded size. The contents come from a
# vzdump restore (`pct restore <id> <backup> --storage local-lvm`) or by replaying the
# container's own IaC from hosts/<host>/.
set -eu
conf=${1:?usage: lxc-recreate.sh <conf> <template> [--run]}
template=${2:?usage: lxc-recreate.sh <conf> <template> [--run]}
run=${3:-}

get() { sed -n "s/^$1: //p" "$conf"; }
id=$(basename "$conf" | cut -d- -f1)

set -- pct create "$id" "$template"
[ -n "$(get hostname)" ]  && set -- "$@" --hostname "$(get hostname)"
[ -n "$(get cores)" ]     && set -- "$@" --cores "$(get cores)"
[ -n "$(get memory)" ]    && set -- "$@" --memory "$(get memory)"
[ -n "$(get swap)" ]      && set -- "$@" --swap "$(get swap)"
[ -n "$(get ostype)" ]    && set -- "$@" --ostype "$(get ostype)"
[ -n "$(get arch)" ]      && set -- "$@" --arch "$(get arch)"
[ -n "$(get nameserver)" ] && set -- "$@" --nameserver "$(get nameserver)"
[ -n "$(get features)" ]  && set -- "$@" --features "$(get features)"
[ -n "$(get onboot)" ]    && set -- "$@" --onboot "$(get onboot)"
[ -n "$(get dev0)" ]      && set -- "$@" --dev0 "$(get dev0)"

# rootfs keeps its size and storage, not its volume name: the volume is new.
rootfs=$(get rootfs)
if [ -n "$rootfs" ]; then
    storage=$(printf '%s' "$rootfs" | cut -d: -f1)
    size=$(printf '%s' "$rootfs" | sed -n 's/.*size=\([0-9]*[GMT]\).*/\1/p')
    set -- "$@" --rootfs "$storage:${size:-8G}"
fi

# net0 keeps the MAC on purpose: the LAN reserves addresses for those MACs.
[ -n "$(get net0)" ] && set -- "$@" --net0 "$(get net0)"

# skynet is privileged (no `unprivileged: 1` line); everything else is not.
if grep -q '^unprivileged: 1' "$conf"; then set -- "$@" --unprivileged 1; fi

printf '%s\n' "$*"
[ "$run" = "--run" ] && "$@"
exit 0
