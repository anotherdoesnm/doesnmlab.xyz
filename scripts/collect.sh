#!/bin/sh
# Re-collect state from the hosts into this repository, with secrets replaced by
# ${VARIABLES}. Run before committing; review the diff, then fill .env if new
# variables appeared.
set -eu
cd "$(dirname "$0")/.."

ssh_vps()  { ssh vps "$@"; }

collect_compose() {  # host sshfn
    host=$1; fn=$2
    $fn 'find /root /opt /srv -maxdepth 3 \( -name docker-compose.y*ml -o -name compose.y*ml \) 2>/dev/null' |
    while read -r path; do
        dest="hosts/$host/compose/$(echo "$path" | sed 's|^/||')"
        mkdir -p "$(dirname "$dest")"
        $fn "cat $path" | sed -E 's/^(\s*-?\s*[A-Za-z0-9_]*(PASSWORD|SECRET|TOKEN)[A-Za-z0-9_]*\s*[:=]\s*)[^$].*/\1${&}/I' > "$dest"
    done
}

collect_compose vps ssh_vps
echo "collected; now review: git diff"
