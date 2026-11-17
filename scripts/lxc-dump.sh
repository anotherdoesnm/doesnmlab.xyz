#!/bin/sh
# Dump every LXC definition on the Proxmox node into hosts/pve/lxc/.
# Run on the node (it needs `pct`, which the agent's restricted shell does not grant
# for anything but list/status/config/exec — hence the copy-paste friendly output).
#
#   sh lxc-dump.sh            # print
#   sh lxc-dump.sh > /dev/null   # same, files are written next to this script
#
# The configs are the source of truth for resources, network, features and onboot.
# The root filesystem is not: that comes from a vzdump backup or from rebuilding the
# container and replaying its own IaC (hosts/<host>/…).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out="$here/../hosts/pve/lxc"
mkdir -p "$out"

pct list | awk 'NR > 1 { print $1 }' | while read -r id; do
    name=$(pct config "$id" | sed -n 's/^hostname: //p')
    pct config "$id" > "$out/$id-$name.conf"
    echo "wrote $out/$id-$name.conf" >&2
done
